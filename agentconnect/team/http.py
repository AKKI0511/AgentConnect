"""HTTP binding for agent-to-team Runtime operations.

Routes match ``spec/bindings/http.md``. This is the Session binding, not
the later gateway. Embedded serving binds loopback only. The Team MCP
server is mounted at ``/mcp``. Loopback calls with no Authorization
header run as the reserved ``operator`` Membership.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from agentconnect.team.errors import TeamError
from agentconnect.team.runtime import Team

HTTP_PREFIX = "/agentconnect/v1"

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
    "internal": 500,
    "unsupported_collect_mode": 501,
    "unavailable": 503,
}

_NO_STORE = {"Cache-Control": "no-store"}
_TOKEN_ISSUE_FIELDS = {"name", "agent_did", "ttl_seconds", "single_use"}


def create_runtime_app(team: Team) -> FastAPI:
    """Return an ASGI app that serves ``team`` at ``/agentconnect/v1`` and ``/mcp``."""
    from agentconnect.mcp.server import create_team_mcp

    mcp = create_team_mcp(team)
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
        return JSONResponse(body, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/join")
    async def join(request: Request) -> JSONResponse:
        """Open a Session."""
        body = await _json_object(request)
        result = await team.join(request=body)
        return JSONResponse(result, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/session/disconnect")
    async def disconnect(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Close this Session. Membership is retained."""
        token = await _session_token(team, request, authorization)
        await team.disconnect(token)
        return Response(status_code=204)

    @app.post(HTTP_PREFIX + "/session/heartbeat")
    async def heartbeat(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """Refresh Session expiry."""
        token = await _session_token(team, request, authorization)
        result = await team.heartbeat(token)
        return JSONResponse(result, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/messages")
    async def send(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Accept a Message."""
        token = await _session_token(team, request, authorization)
        body = await _json_object(request)
        result = await team.send(token, body)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/mailbox/lease")
    async def lease(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Lease work from this Membership's Mailbox."""
        token = await _session_token(team, request, authorization)
        body = await _json_object(request, empty_ok=True)
        max_items = body.get("max_items", 1)
        result = await team.lease(token, max_items)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/deliveries/complete")
    async def complete(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Finish a Delivery without a response Message."""
        token = await _session_token(team, request, authorization)
        body = await _json_object(request)
        lease_id = body.get("lease_id")
        if not isinstance(lease_id, str):
            raise TeamError("invalid_request", "lease_id is required")
        result = await team.complete(token, lease_id)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/deliveries/reply")
    async def reply(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Finish a leased reply-expected Delivery."""
        token = await _session_token(team, request, authorization)
        body = await _json_object(request)
        result = await team.reply(token, body)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/tickets/{ticket_id}")
    async def get_result(
        request: Request,
        ticket_id: str,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """Return a Ticket this Session's Membership owns."""
        token = await _session_token(team, request, authorization)
        result = await team.get_result(token, ticket_id)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/threads/{thread_id}/history")
    async def get_history(
        request: Request,
        thread_id: str,
        authorization: Optional[str] = Header(default=None),
        before: Optional[str] = Query(default=None),
        limit: int = Query(default=50),
    ) -> JSONResponse:
        """Return one page of retained Thread history."""
        token = await _session_token(team, request, authorization)
        result = await team.get_history(token, thread_id, before=before, limit=limit)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/directory/find")
    async def find(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Search this Team's Directory."""
        token = await _session_token(team, request, authorization)
        body = await _json_object(request)
        query = body.get("query")
        if not isinstance(query, str):
            raise TeamError("invalid_request", "query is required")
        result = await team.find(
            token,
            query,
            limit=body.get("limit"),
            detail=body.get("detail", "summary"),
        )
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/directory/members/{address}")
    async def get_profile(
        request: Request,
        address: str,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """Return one Directory entry."""
        token = await _session_token(team, request, authorization)
        result = await team.get_profile(token, address)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/status")
    async def status(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Return members, online state, Mailbox depths, and open Tickets."""
        token = await _session_token(team, request, authorization)
        result = await team.status(token)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/traces/events")
    async def trace_events(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> StreamingResponse:
        """Stream new Trace events. Operator only."""
        token = await _session_token(team, request, authorization)
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
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """Return the recorded timeline for one ``trace_id``."""
        token = await _session_token(team, request, authorization)
        result = await team.get_trace(token, trace_id)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/tokens")
    async def issue_join_token(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Issue a join token. Operator only."""
        token = await _session_token(team, request, authorization)
        await team._require_operator(token)
        body = await _json_object(request, empty_ok=True)
        extra = set(body.keys()) - _TOKEN_ISSUE_FIELDS
        if extra:
            raise TeamError("invalid_request", "token body contains unsupported fields")
        ttl = body.get("ttl_seconds")
        ttl_seconds = None
        if ttl is not None:
            if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
                raise TeamError("invalid_request", "ttl_seconds must be a number")
            ttl_seconds = float(ttl)
        single_use = body.get("single_use", False)
        if not isinstance(single_use, bool):
            raise TeamError("invalid_request", "single_use must be a boolean")
        name = body.get("name")
        agent_did = body.get("agent_did")
        if name is not None and not isinstance(name, str):
            raise TeamError("invalid_request", "name must be a string")
        if agent_did is not None and not isinstance(agent_did, str):
            raise TeamError("invalid_request", "agent_did must be a string")
        result = await team.issue_join_token(
            name=name,
            agent_did=agent_did,
            ttl_seconds=ttl_seconds,
            single_use=single_use,
        )
        return JSONResponse(dict(result), headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/tokens/revoke")
    async def revoke_join_token(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> Response:
        """Revoke a join token. Operator only."""
        token = await _session_token(team, request, authorization)
        await team._require_operator(token)
        body = await _json_object(request)
        extra = set(body.keys()) - {"token"}
        if extra:
            raise TeamError("invalid_request", "token body contains unsupported fields")
        secret = body.get("token")
        if not isinstance(secret, str) or not secret.strip():
            raise TeamError("invalid_request", "token is required")
        await team.revoke_join_token(secret.strip())
        return Response(status_code=204)

    @app.get(HTTP_PREFIX + "/session/events")
    async def session_events(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> StreamingResponse:
        """Stream work hints for this Session."""
        token = await _session_token(team, request, authorization)
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
    return app


async def _session_token(
    team: Team, request: Request, authorization: Optional[str]
) -> str:
    """Return a Session token, using the loopback operator when none is sent."""
    if authorization:
        if not authorization.lower().startswith("bearer "):
            raise TeamError("unauthorized", "Session is missing or invalid")
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise TeamError("unauthorized", "Session is missing or invalid")
        return token
    if _client_is_loopback(request):
        return await team.ensure_operator_session()
    raise TeamError("unauthorized", "Session is missing or invalid")


def _client_is_loopback(request: Request) -> bool:
    """Return True when the HTTP peer is a loopback address."""
    client = request.client
    if client is None:
        return False
    return _host_is_loopback(client.host)


def _host_is_loopback(host: str) -> bool:
    """Return True when ``host`` is loopback, including IPv4-mapped IPv6."""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    if addr.is_loopback:
        return True
    mapped = getattr(addr, "ipv4_mapped", None)
    return mapped is not None and mapped.is_loopback


async def _json_object(request: Request, *, empty_ok: bool = False) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        if empty_ok and (request.headers.get("content-length") in {None, "0"}):
            return {}
        raise TeamError("invalid_request", "Request body must be a JSON object")
    if body is None and empty_ok:
        return {}
    if not isinstance(body, dict):
        raise TeamError("invalid_request", "Request body must be a JSON object")
    return body


def _error_response(exc: TeamError) -> JSONResponse:
    status = _STATUS.get(exc.code, 500)
    body = exc.to_error_object()
    if "retryable" not in body:
        body["retryable"] = status in {429, 503}
    headers = dict(_NO_STORE) if status in {401} else None
    return JSONResponse(body, status_code=status, headers=headers)
