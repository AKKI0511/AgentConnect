"""HTTP binding for agent-to-team Runtime operations.

Routes match ``spec/bindings/http.md``. This is the Session binding, not
the later gateway. Embedded serving binds loopback only. The Team MCP
server is mounted at ``/mcp``.
"""

from __future__ import annotations

import asyncio
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
        authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Close this Session. Membership is retained."""
        token = _bearer(authorization)
        await team.disconnect(token)
        return Response(status_code=204)

    @app.post(HTTP_PREFIX + "/session/heartbeat")
    async def heartbeat(
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """Refresh Session expiry."""
        token = _bearer(authorization)
        result = await team.heartbeat(token)
        return JSONResponse(result, headers=_NO_STORE)

    @app.post(HTTP_PREFIX + "/messages")
    async def send(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Accept a Message."""
        token = _bearer(authorization)
        body = await _json_object(request)
        result = await team.send(token, body)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/mailbox/lease")
    async def lease(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Lease work from this Membership's Mailbox."""
        token = _bearer(authorization)
        body = await _json_object(request, empty_ok=True)
        max_items = body.get("max_items", 1)
        result = await team.lease(token, max_items)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/deliveries/complete")
    async def complete(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Finish a Delivery without a response Message."""
        token = _bearer(authorization)
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
        token = _bearer(authorization)
        body = await _json_object(request)
        result = await team.reply(token, body)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/tickets/{ticket_id}")
    async def get_result(
        ticket_id: str, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Return a Ticket this Session's Membership owns."""
        token = _bearer(authorization)
        result = await team.get_result(token, ticket_id)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/threads/{thread_id}/history")
    async def get_history(
        thread_id: str,
        authorization: Optional[str] = Header(default=None),
        before: Optional[str] = Query(default=None),
        limit: int = Query(default=50),
    ) -> JSONResponse:
        """Return one page of retained Thread history."""
        token = _bearer(authorization)
        result = await team.get_history(token, thread_id, before=before, limit=limit)
        return JSONResponse(result)

    @app.post(HTTP_PREFIX + "/directory/find")
    async def find(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Search this Team's Directory."""
        token = _bearer(authorization)
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
        address: str, authorization: Optional[str] = Header(default=None)
    ) -> JSONResponse:
        """Return one Directory entry."""
        token = _bearer(authorization)
        result = await team.get_profile(token, address)
        return JSONResponse(result)

    @app.get(HTTP_PREFIX + "/session/events")
    async def session_events(
        request: Request, authorization: Optional[str] = Header(default=None)
    ) -> StreamingResponse:
        """Stream work hints for this Session."""
        token = _bearer(authorization)
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


def _bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise TeamError("unauthorized", "Session is missing or invalid")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise TeamError("unauthorized", "Session is missing or invalid")
    return token


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
