"""HTTP client for agent-to-team Runtime operations.

POST for every operation except Ticket and history reads. SSE on
``GET /session/events`` is a work hint, not a correctness channel.

This binding is the agent Session over HTTP. It is not the gateway
outbound stack in ``transport/http.py``.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Mapping
from urllib.parse import quote

import httpx

from agentconnect.transport.runtime import TransportError

AGENTCONNECT_V1 = "/agentconnect/v1"

# Proxies drop idle connections well before a 24h wait. After this many
# seconds a wait send falls back to get_result (SI-002).
WAIT_HOLD_SECONDS = 25.0

_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

_HTTP_ERROR_STATUS = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "id_conflict",
    413: "payload_too_large",
    429: "busy",
    500: "internal",
    501: "unsupported_collect_mode",
    503: "unavailable",
}


def normalize_runtime_url(url: str) -> str:
    """Return the Runtime origin plus ``/agentconnect/v1`` without a trailing slash."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("join URL must be a non-empty string")
    origin = url.strip().rstrip("/")
    if origin.endswith(AGENTCONNECT_V1):
        return origin
    return origin + AGENTCONNECT_V1


class HttpRuntimeTransport:
    """Runtime operations over HTTP POST and an optional SSE event stream."""

    def __init__(self, url: str, *, timeout: float = 30.0) -> None:
        """Connect to a Runtime origin. ``url`` may omit ``/agentconnect/v1``."""
        self._base = normalize_runtime_url(url)
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(5.0, timeout))
        )

    async def join_challenge(self) -> dict[str, Any]:
        """GET /join/challenge."""
        return await self._request("GET", "/join/challenge", auth=None)

    async def join(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """POST /join."""
        return await self._request("POST", "/join", json=dict(request), auth=None)

    async def disconnect(self, session_token: str) -> None:
        """POST /session/disconnect."""
        await self._request(
            "POST", "/session/disconnect", auth=session_token, expect_json=False
        )

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """POST /session/heartbeat."""
        return await self._request("POST", "/session/heartbeat", auth=session_token)

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """POST /messages. A ``wait`` send falls back to get_result after 25s."""
        body = dict(request)
        timeout = self._timeout
        if body.get("collect") == "wait":
            timeout = WAIT_HOLD_SECONDS
        try:
            return await self._request(
                "POST",
                "/messages",
                json=body,
                auth=session_token,
                timeout=timeout,
            )
        except httpx.TimeoutException:
            ticket_id = body.get("id")
            if not isinstance(ticket_id, str) or body.get("collect") != "wait":
                raise TransportError(
                    "unavailable",
                    "send timed out before the Runtime accepted it",
                    retryable=True,
                )
            return await self._recover_wait(session_token, ticket_id)

    async def _recover_wait(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """After a dropped wait connection, poll get_result until terminal."""
        while True:
            try:
                ticket = await self.get_result(session_token, ticket_id)
            except TransportError as exc:
                if exc.code == "not_found":
                    raise TransportError(
                        "unavailable",
                        "wait send was interrupted before acceptance",
                        retryable=True,
                    ) from exc
                raise
            if ticket.get("state") != "open":
                return {
                    "status": "ticketed",
                    "message": {
                        "id": ticket_id,
                        "sender": ticket.get("requester"),
                        "recipient": ticket.get("recipient"),
                        "kind": "request",
                        "content": None,
                        "created_at": ticket.get("created_at"),
                        "trace_id": ticket_id,
                        "deadline": ticket.get("deadline"),
                    },
                    "ticket": ticket,
                }
            await _sleep(0.1)

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """POST /mailbox/lease."""
        return await self._request(
            "POST",
            "/mailbox/lease",
            json={"max_items": max_items},
            auth=session_token,
        )

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """POST /deliveries/complete."""
        return await self._request(
            "POST",
            "/deliveries/complete",
            json={"lease_id": lease_id},
            auth=session_token,
        )

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """POST /deliveries/reply."""
        return await self._request(
            "POST", "/deliveries/reply", json=dict(request), auth=session_token
        )

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """GET /tickets/{ticket_id}."""
        return await self._request(
            "GET", f"/tickets/{quote(ticket_id, safe='')}", auth=session_token
        )

    async def get_history(
        self,
        session_token: str,
        thread_id: str,
        *,
        before: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """GET /threads/{thread_id}/history."""
        params: dict[str, Any] = {"limit": limit}
        if before is not None:
            params["before"] = before
        return await self._request(
            "GET",
            f"/threads/{quote(thread_id, safe='')}/history",
            params=params,
            auth=session_token,
        )

    async def find(
        self,
        session_token: str,
        query: str,
        *,
        limit: int = 10,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """POST /directory/find."""
        return await self._request(
            "POST",
            "/directory/find",
            json={"query": query, "limit": limit, "detail": detail},
            auth=session_token,
        )

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """GET /directory/members/{address}."""
        return await self._request(
            "GET",
            f"/directory/members/{quote(address, safe='')}",
            auth=session_token,
        )

    async def events(self, session_token: str) -> AsyncIterator[dict[str, Any]]:
        """GET /session/events. Yields work hints, not a correctness channel."""
        url = self._base + "/session/events"
        headers = {
            "Authorization": f"Bearer {session_token}",
            "Accept": "text/event-stream",
        }
        try:
            async with self._client.stream(
                "GET", url, headers=headers, timeout=None
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise self._error_from_response(response.status_code, body)
                event_type = "message"
                data_lines: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_type = line[6:].strip() or "message"
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                    elif line == "":
                        if data_lines:
                            raw = "\n".join(data_lines)
                            try:
                                data = json.loads(raw) if raw else {}
                            except json.JSONDecodeError:
                                data = {}
                            if not isinstance(data, dict):
                                data = {}
                            yield {"type": event_type, "data": data}
                        event_type = "message"
                        data_lines = []
        except httpx.RequestError as exc:
            raise TransportError(
                "unavailable", str(exc) or "event stream closed", retryable=True
            ) from exc

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        auth: str | None = "",
        expect_json: bool = True,
        timeout: float | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        if json is not None:
            headers["Content-Type"] = "application/json"
        url = self._base + path
        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                json=None if json is None else dict(json),
                params=None if params is None else dict(params),
                timeout=timeout,
            )
        except httpx.TimeoutException:
            raise
        except httpx.RequestError as exc:
            raise TransportError(
                "unavailable", str(exc) or "Runtime is unreachable", retryable=True
            ) from exc
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            raise self._error_from_response(response.status_code, response.content)
        if not expect_json:
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            raise TransportError("internal", "Runtime returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TransportError("internal", "Runtime returned a non-object result")
        return payload

    @staticmethod
    def _error_from_response(status_code: int, raw: bytes) -> TransportError:
        body: Any = None
        try:
            body = json.loads(raw.decode("utf-8") or "null")
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = None
        if isinstance(body, dict) and body.get("code"):
            error = TransportError.from_error_object(body)
            if error.retryable is None:
                error.retryable = status_code in _RETRYABLE_STATUS
            return error
        code = _HTTP_ERROR_STATUS.get(status_code, "internal")
        return TransportError(
            code,
            f"HTTP {status_code}",
            retryable=status_code in _RETRYABLE_STATUS,
        )


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
