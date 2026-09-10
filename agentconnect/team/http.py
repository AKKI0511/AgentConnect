"""HTTP binding for agent-to-team Runtime operations.

Routes match ``spec/bindings/http.md``. This is the Session binding, not
the later gateway. Loopback serving binds loopback only. Loopback calls with
no Authorization header run as the reserved ``operator`` principal Membership
only when the HTTP peer is loopback and the request has no forwarded-client
headers, including empty ``X-Forwarded-*`` values.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from agentconnect.core.base import dump_public
from agentconnect.core.operations import (
    GetHistoryRequest,
    parse_complete_request,
    parse_find_request,
    parse_issue_join_token_request,
    parse_lease_request,
    parse_renew_request,
    parse_revoke_join_token_request,
    parse_schema,
)
from agentconnect.team.constants import DEFAULT_MAX_MESSAGE_BYTES
from agentconnect.team.errors import TeamError
from agentconnect.team.runtime import Team
from agentconnect.team.session_auth import session_token_for_request

HTTP_PREFIX = "/agentconnect/v1"
_NO_STORE = {"Cache-Control": "no-store"}

_STATUS = {
    "unsupported_version": 400,
    "invalid_request": 400,
    "invalid_address": 400,
    "address_outside_team": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "name_conflict": 409,
    "id_conflict": 409,
    "lease_expired": 409,
    "ticket_closed": 409,
    "payload_too_large": 413,
    "busy": 429,
    "wait_limit": 429,
    "internal": 500,
    "unavailable": 503,
}


def _json(body: Any, **kwargs: Any) -> JSONResponse:
    """Serialize a public schema object or mapping as JSON."""
    return JSONResponse(dump_public(body), **kwargs)


def _wire(parse_fn, body: Any):
    """Parse a wire body or raise ``invalid_request``."""
    try:
        return parse_fn(body)
    except ValueError as exc:
        raise TeamError("invalid_request", str(exc)) from exc


_PUBLIC_PATHS = frozenset(
    {
        HTTP_PREFIX + "/join",
        HTTP_PREFIX + "/join/challenge",
    }
)


class SessionAuthMiddleware:
    """Authenticate Runtime HTTP routes once and store the Session on the request."""

    def __init__(self, app: ASGIApp, team: Team) -> None:
        """Bind the ASGI app and the Team whose Sessions are checked."""
        self.app = app
        self.team = team

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Resolve a live Session for protected Runtime HTTP routes."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if not str(path).startswith(HTTP_PREFIX) or path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        client = scope.get("client")
        peer_host = client[0] if isinstance(client, (tuple, list)) and client else None
        try:
            token = await session_token_for_request(
                self.team,
                headers,
                peer_host=peer_host,
                in_process=False,
            )
        except TeamError as exc:
            response = _error_response(exc)
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})
        scope["state"]["session_token"] = token
        await self.app(scope, receive, send)


def _bound_session(request: Request) -> str:
    """Return the Session token stored by :class:`SessionAuthMiddleware`."""
    token = getattr(request.state, "session_token", None)
    if not isinstance(token, str) or not token:
        raise TeamError("unauthorized", "Session is missing or invalid")
    return token


def create_runtime_app(team: Team) -> FastAPI:
    """Return an ASGI app that serves ``team`` at ``/agentconnect/v1`` and ``/mcp``."""
    from agentconnect.mcp.server import create_team_mcp

    mcp = create_team_mcp(team, in_process=False)
    team._mcp = mcp
    mcp_asgi = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="127.0.0.1",
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="AgentConnect Runtime",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.team = team

    @app.exception_handler(TeamError)
    async def team_error_handler(_request: Request, exc: TeamError) -> JSONResponse:
        """Map a TeamError onto an HTTP error object."""
        return _error_response(exc)

    @app.get(HTTP_PREFIX + "/join/challenge")
    async def join_challenge() -> JSONResponse:
        """Return a one-time join challenge for an identity proof."""
        body = await team.join_challenge()
        return _json(body, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/join")
    async def join(request: Request) -> JSONResponse:
        """Open a Session."""
        body = await _json_object(request)
        result = await team.join(request=body)
        return _json(result, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/session/disconnect")
    async def disconnect(
        request: Request,
    ) -> Response:
        """Close this Session. Membership is retained."""
        token = _bound_session(request)
        await team.disconnect(token)
        return Response(status_code=204)

    @app.post(HTTP_PREFIX + "/session/heartbeat")
    async def heartbeat(
        request: Request,
    ) -> JSONResponse:
        """Refresh Session expiry."""
        token = _bound_session(request)
        result = await team.heartbeat(token)
        return _json(result, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/messages")
    async def send(request: Request) -> JSONResponse:
        """Accept a Message."""
        token = _bound_session(request)
        body = await _json_object(request)
        result = await team.send(token, body)
        return _json(result)

    @app.post(HTTP_PREFIX + "/mailbox/lease")
    async def lease(request: Request) -> JSONResponse:
        """Lease work from this Membership's Mailbox."""
        token = _bound_session(request)
        body = await _json_object(request, empty_ok=True)
        parsed = _wire(parse_lease_request, body)
        max_items = 1 if parsed.max_items is None else parsed.max_items
        result = await team.lease(token, max_items)
        return _json(result)

    @app.post(HTTP_PREFIX + "/deliveries/renew")
    async def renew(request: Request) -> JSONResponse:
        """Extend one active Delivery lease."""
        token = _bound_session(request)
        body = await _json_object(request)
        parsed = _wire(parse_renew_request, body)
        result = await team.renew(token, parsed.lease_id)
        return _json(result)

    @app.post(HTTP_PREFIX + "/deliveries/complete")
    async def complete(request: Request) -> JSONResponse:
        """Finish a Delivery without a response Message."""
        token = _bound_session(request)
        body = await _json_object(request)
        parsed = _wire(parse_complete_request, body)
        result = await team.complete(token, parsed.lease_id)
        return _json(result)

    @app.post(HTTP_PREFIX + "/deliveries/reply")
    async def reply(request: Request) -> JSONResponse:
        """Finish a leased reply-expected Delivery."""
        token = _bound_session(request)
        body = await _json_object(request)
        result = await team.reply(token, body)
        return _json(result)

    @app.get(HTTP_PREFIX + "/tickets/{ticket_id}")
    async def get_result(
        request: Request,
        ticket_id: str,
    ) -> JSONResponse:
        """Return a Ticket this Session's Membership owns."""
        token = _bound_session(request)
        result = await team.get_result(token, ticket_id)
        return _json(result)

    @app.get(HTTP_PREFIX + "/threads/{thread_id}/history")
    async def get_history(
        request: Request,
        thread_id: str,
        before: Optional[str] = Query(default=None),
        limit: int = Query(default=50),
    ) -> JSONResponse:
        """Return one page of retained Thread history."""
        token = _bound_session(request)
        parsed = _wire(
            lambda payload: parse_schema(GetHistoryRequest, payload),
            {
                "thread_id": thread_id,
                **({"before": before} if before is not None else {}),
                "limit": limit,
            },
        )
        result = await team.get_history(
            token, parsed.thread_id, before=parsed.before, limit=parsed.limit or 50
        )
        return _json(result)

    @app.post(HTTP_PREFIX + "/directory/find")
    async def find(request: Request) -> JSONResponse:
        """Search this Team's Directory."""
        token = _bound_session(request)
        body = await _json_object(request)
        parsed = _wire(parse_find_request, body)
        result = await team.find(
            token,
            parsed.query,
            limit=parsed.limit,
            detail=parsed.detail,
        )
        return _json(result)

    @app.get(HTTP_PREFIX + "/directory/members/{address}")
    async def get_profile(
        request: Request,
        address: str,
    ) -> JSONResponse:
        """Return one Directory entry."""
        token = _bound_session(request)
        result = await team.get_profile(token, address)
        return _json(result)

    @app.get(HTTP_PREFIX + "/status")
    async def status(request: Request) -> JSONResponse:
        """Return members, online state, Mailbox depths, and open Tickets."""
        token = _bound_session(request)
        result = await team.status(token)
        return _json(result)

    @app.get(HTTP_PREFIX + "/traces/events")
    async def trace_events(request: Request) -> StreamingResponse:
        """Stream new Trace events. Operator only."""
        token = _bound_session(request)
        queue = await team.subscribe_trace_events(token)

        async def generate_trace():
            """Yield SSE frames until the client disconnects."""
            try:
                yield ": keepalive\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if event is None:
                        break
                    yield f"event: trace\ndata: {json.dumps(event)}\n\n"
            finally:
                await team.unsubscribe_trace_events(token, queue)

        return StreamingResponse(
            generate_trace(),
            media_type="text/event-stream",
            headers=_NO_STORE,
        )

    @app.get(HTTP_PREFIX + "/traces/{trace_id}")
    async def get_trace(
        request: Request,
        trace_id: str,
    ) -> JSONResponse:
        """Return the recorded timeline for one ``trace_id``."""
        token = _bound_session(request)
        result = await team.get_trace(token, trace_id)
        return _json(result)

    @app.post(HTTP_PREFIX + "/tokens")
    async def issue_join_token(request: Request) -> JSONResponse:
        """Issue a join token. Operator only."""
        token = _bound_session(request)
        await team._require_operator(token)
        body = await _json_object(request, empty_ok=True)
        parsed = _wire(parse_issue_join_token_request, body)
        result = await team.issue_join_token(
            name=parsed.name,
            agent_did=parsed.agent_did,
            ttl_seconds=parsed.ttl_seconds,
            single_use=False if parsed.single_use is None else parsed.single_use,
        )
        return _json(result, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/tokens/revoke")
    async def revoke_join_token(request: Request) -> Response:
        """Revoke a join token. Operator only."""
        token = _bound_session(request)
        await team._require_operator(token)
        body = await _json_object(request)
        parsed = _wire(parse_revoke_join_token_request, body)
        await team.revoke_join_token(parsed.token)
        return Response(status_code=204)

    @app.get(HTTP_PREFIX + "/session/events")
    async def session_events(request: Request) -> StreamingResponse:
        """Stream work hints for this Session."""
        token = _bound_session(request)
        queue = await team.subscribe_events(token)

        async def generate():
            """Yield SSE frames until the client disconnects."""
            try:
                yield ": keepalive\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if event is None:
                        break
                    event_type = event.get("type") or "message"
                    data = (
                        event.get("data") if isinstance(event.get("data"), dict) else {}
                    )
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            finally:
                await team.unsubscribe_events(token, queue)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers=_NO_STORE,
        )

    app.mount("/mcp", mcp_asgi)
    app.add_middleware(SessionAuthMiddleware, team=team)
    return app


async def _json_object(request: Request, *, empty_ok: bool = False) -> dict[str, Any]:
    """Read a JSON object body, capped at the Team ``max_message_bytes``.

    When ``Content-Length`` exceeds that budget this fails before the rest
    of the body is read. When it is absent, reading stops after the cap.
    """
    team = getattr(request.app.state, "team", None)
    max_bytes = int(getattr(team, "max_message_bytes", DEFAULT_MAX_MESSAGE_BYTES))
    length_header = request.headers.get("content-length")
    if length_header is not None:
        try:
            length = int(length_header)
        except ValueError:
            raise TeamError("invalid_request", "Request body must be a JSON object")
        if length < 0:
            raise TeamError("invalid_request", "Request body must be a JSON object")
        if length > max_bytes:
            raise TeamError(
                "payload_too_large", "Request body exceeds max_message_bytes"
            )
        if length == 0 and empty_ok:
            return {}
    chunks = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        if len(chunks) + len(chunk) > max_bytes:
            raise TeamError(
                "payload_too_large", "Request body exceeds max_message_bytes"
            )
        chunks.extend(chunk)
    if not chunks:
        if empty_ok:
            return {}
        raise TeamError("invalid_request", "Request body must be a JSON object")
    try:
        body = json.loads(bytes(chunks))
    except Exception:
        raise TeamError("invalid_request", "Request body must be a JSON object")
    if body is None and empty_ok:
        return {}
    if not isinstance(body, dict):
        raise TeamError("invalid_request", "Request body must be a JSON object")
    return body


def _error_response(exc: TeamError) -> JSONResponse:
    """Map a TeamError to an HTTP JSON error response."""
    status = _STATUS.get(exc.code, 500)
    body = exc.to_error_object()
    if "retryable" not in body:
        body["retryable"] = status in {429, 503}
    headers = dict(_NO_STORE) if status in {401} else None
    return JSONResponse(dump_public(body), status_code=status, headers=headers)
