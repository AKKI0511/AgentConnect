"""HTTP operations and optional SSE work hints for an Agent Session."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import AsyncIterator, TypeVar

from agentconnect.core.base import JsonObject, JsonValue, dump_public, parse_schema
from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.operations import (
    CompleteResult,
    HeartbeatResult,
    HistoryResult,
    JoinChallenge,
    JoinRequest,
    JoinResult,
    LeaseResult,
    RenewResult,
    ReplyRequest,
    ReplyResult,
    RuntimeEvent,
    SendRequest,
    SendResult,
    parse_history_result,
    parse_join_result,
    parse_lease_result,
    parse_send_result,
)
from agentconnect.core.ticket import Ticket, parse_ticket
from agentconnect.core.primitives import Address, SessionToken, Uuid
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter

from agentconnect.transport.runtime import TransportError

_Result = TypeVar("_Result")
_ERROR_JSON: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


def _parse_result(parser: Callable[[object], _Result], data: object) -> _Result:
    """Validate external Runtime output through the transport error boundary."""
    try:
        return parser(data)
    except ValueError as exc:
        raise TransportError("internal", "Runtime returned an invalid result") from exc


AGENTCONNECT_V1 = "/agentconnect/v1"

_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

_SEND_TIMEOUT_MESSAGE = (
    "send timed out; the Runtime may already have accepted the Message"
)


def _is_timeout_failure(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    return isinstance(exc, TransportError) and isinstance(
        exc.__cause__, httpx.TimeoutException
    )


_HTTP_ERROR_STATUS = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "id_conflict",
    413: "payload_too_large",
    429: "busy",
    500: "internal",
    503: "unavailable",
}


def normalize_runtime_url(url: str) -> str:
    """Return the Runtime origin plus `/agentconnect/v1` without a trailing slash.

    Args:
        url: Runtime origin, with or without `/agentconnect/v1`.

    Raises:
        ValueError: `url` is empty.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("join URL must be a non-empty string")
    origin = url.strip().rstrip("/")
    if origin.endswith(AGENTCONNECT_V1):
        return origin
    return origin + AGENTCONNECT_V1


class HttpRuntimeTransport:
    """Use RuntimeTransport operations against a served Team over HTTP.

    Owns an HTTP client that must be closed. Session tokens are sent as Bearer
    credentials after admission; constructing the transport does not join.
    Runtime error bodies retain their public codes and details. Network failures
    become `unavailable`, and cancellation propagates.

    See `RuntimeTransport` for result shapes and operation authority.
    """

    def __init__(self, url: str, *, timeout: float = 30.0) -> None:
        """Prepare connectivity to the Runtime origin or its `/agentconnect/v1` URL.

        Args:
            timeout: Finite ordinary request timeout in seconds. Connection setup
                waits at most five seconds, or this shorter bound. Sends may wait
                longer to cover the Runtime's collection hold.

        Raises:
            ValueError: The URL is empty.
        """
        self._base = normalize_runtime_url(url)
        self._timeout = timeout
        self._wait_hold_seconds = 25.0
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(5.0, timeout))
        )

    def configure_wait_hold(self, wait_hold_seconds: float) -> None:
        """Set the Runtime wait hold reported at join.

        Subsequent send timeouts use the greater of the ordinary timeout and this
        hold plus five seconds. This changes waiting, rather than a work deadline.
        """
        self._wait_hold_seconds = max(0.0, float(wait_hold_seconds))

    def _send_timeout(self) -> float:
        return max(self._timeout, self._wait_hold_seconds + 5.0)

    async def join_challenge(self) -> JoinChallenge:
        """Fetch a fresh identity-proof challenge over HTTP without Session authentication."""
        return _parse_result(
            lambda data: parse_schema(JoinChallenge, data),
            await self._request("GET", "/join/challenge", auth=None),
        )

    async def join(self, request: JoinRequest) -> JoinResult:
        """Open a Session over HTTP with admission credentials in the JoinRequest body."""
        return _parse_result(
            parse_join_result,
            await self._request("POST", "/join", json=dump_public(request), auth=None),
        )

    async def disconnect(self, session_token: SessionToken) -> None:
        """End the Session over HTTP; its Membership and accepted work remain."""
        await self._request(
            "POST", "/session/disconnect", auth=session_token, expect_json=False
        )

    async def heartbeat(self, session_token: SessionToken) -> HeartbeatResult:
        """Renew Session expiry over HTTP; ordinary authenticated calls do not renew it."""
        return _parse_result(
            lambda data: parse_schema(HeartbeatResult, data),
            await self._request("POST", "/session/heartbeat", auth=session_token),
        )

    async def send(
        self, session_token: SessionToken, request: SendRequest
    ) -> SendResult:
        """Submit work over HTTP and retry once on timeout with the identical body.

        The send timeout covers the negotiated Runtime wait hold. If both attempts
        time out, raises `TransportError` with `unavailable`; the Message may already
        be accepted. Keep its id to recover the result rather than submitting new work.
        Other connection failures are surfaced without this timeout retry.
        """
        body = dump_public(request)
        timeout = self._send_timeout()
        try:
            return _parse_result(
                parse_send_result,
                await self._request(
                    "POST",
                    "/messages",
                    json=body,
                    auth=session_token,
                    timeout=timeout,
                ),
            )
        except (httpx.TimeoutException, TransportError) as exc:
            if not _is_timeout_failure(exc):
                raise
            try:
                return _parse_result(
                    parse_send_result,
                    await self._request(
                        "POST",
                        "/messages",
                        json=body,
                        auth=session_token,
                        timeout=timeout,
                    ),
                )
            except (httpx.TimeoutException, TransportError) as retry_exc:
                if _is_timeout_failure(retry_exc):
                    raise TransportError(
                        "unavailable",
                        _SEND_TIMEOUT_MESSAGE,
                        retryable=True,
                    ) from retry_exc
                raise

    async def lease(
        self, session_token: SessionToken, max_items: int = 1
    ) -> LeaseResult:
        """Fetch available Delivery attempts over HTTP within Session capacity."""
        return _parse_result(
            parse_lease_result,
            await self._request(
                "POST",
                "/mailbox/lease",
                json={"max_items": max_items},
                auth=session_token,
            ),
        )

    async def renew(self, session_token: SessionToken, lease_id: Uuid) -> RenewResult:
        """Renew an active attempt owned by the Session."""
        return _parse_result(
            lambda data: parse_schema(RenewResult, data),
            await self._request(
                "POST",
                "/deliveries/renew",
                json={"lease_id": lease_id},
                auth=session_token,
            ),
        )

    async def complete(
        self, session_token: SessionToken, lease_id: Uuid
    ) -> CompleteResult:
        """Complete an event or decline a request under an active Session-owned lease."""
        return _parse_result(
            lambda data: parse_schema(CompleteResult, data),
            await self._request(
                "POST",
                "/deliveries/complete",
                json={"lease_id": lease_id},
                auth=session_token,
            ),
        )

    async def reply(
        self, session_token: SessionToken, request: ReplyRequest
    ) -> ReplyResult:
        """Submit a successful or failed reply under an active Session-owned request lease."""
        return _parse_result(
            lambda data: parse_schema(ReplyResult, data),
            await self._request(
                "POST",
                "/deliveries/reply",
                json=dump_public(request),
                auth=session_token,
            ),
        )

    async def get_result(self, session_token: SessionToken, ticket_id: Uuid) -> Ticket:
        """Fetch retained wire Ticket data over HTTP under its owning Membership."""
        return _parse_result(
            parse_ticket,
            await self._request(
                "GET", f"/tickets/{quote(ticket_id, safe='')}", auth=session_token
            ),
        )

    async def get_history(
        self,
        session_token: SessionToken,
        thread_id: Uuid,
        *,
        before: Uuid | None = None,
        limit: int = 50,
    ) -> HistoryResult:
        """Fetch a retained history page over HTTP for a Thread the caller participates in."""
        params: dict[str, str | int] = {"limit": limit}
        if before is not None:
            params["before"] = before
        return _parse_result(
            parse_history_result,
            await self._request(
                "GET",
                f"/threads/{quote(thread_id, safe='')}/history",
                params=params,
                auth=session_token,
            ),
        )

    async def find(
        self,
        session_token: SessionToken,
        query: str,
        *,
        limit: int | None = None,
    ) -> FindResult:
        """Fetch ranked Directory candidates over HTTP."""
        body: JsonObject = {"query": query}
        if limit is not None:
            body["limit"] = limit
        return _parse_result(
            lambda data: parse_schema(FindResult, data),
            await self._request(
                "POST",
                "/directory/find",
                json=body,
                auth=session_token,
            ),
        )

    async def get_profile(
        self, session_token: SessionToken, address: Address
    ) -> DirectoryEntry:
        """Fetch a full Directory entry over HTTP for a same-Team Address."""
        return _parse_result(
            lambda data: parse_schema(DirectoryEntry, data),
            await self._request(
                "GET",
                f"/directory/members/{quote(address, safe='')}",
                auth=session_token,
            ),
        )

    async def events(self, session_token: SessionToken) -> AsyncIterator[RuntimeEvent]:
        """Read SSE work hints with no finite stream timeout.

        Connection errors become `unavailable`. Cancelling or closing the iterator
        releases the stream; this method does not reconnect it. Unknown event types
        are yielded for the client to ignore.
        """
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
                                data: object = json.loads(raw) if raw else {}
                            except json.JSONDecodeError:
                                data = {}
                            if not isinstance(data, dict):
                                data = {}
                            yield _parse_result(
                                lambda raw: parse_schema(RuntimeEvent, raw),
                                {"type": event_type, "data": data},
                            )
                        event_type = "message"
                        data_lines = []
        except httpx.RequestError as exc:
            raise TransportError(
                "unavailable", str(exc) or "event stream closed", retryable=True
            ) from exc

    async def close(self) -> None:
        """Close the owned HTTP client; disconnect the Session separately."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, JsonValue] | None = None,
        params: Mapping[str, str | int] | None = None,
        auth: str | None = "",
        expect_json: bool = True,
        timeout: float | None = None,
    ) -> object:
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        if json is not None:
            headers["Content-Type"] = "application/json"
        url = self._base + path
        try:
            if timeout is None:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=None if json is None else dict(json),
                    params=params,
                )
            else:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=None if json is None else dict(json),
                    params=params,
                    timeout=timeout,
                )
        except httpx.TimeoutException as exc:
            raise TransportError(
                "unavailable",
                "Runtime request timed out",
                retryable=True,
            ) from exc
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
            payload: object = response.json()
        except ValueError as exc:
            raise TransportError("internal", "Runtime returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TransportError("internal", "Runtime returned a non-object result")
        return payload

    @staticmethod
    def _error_from_response(status_code: int, raw: bytes) -> TransportError:
        body: object = None
        try:
            body = json.loads(raw.decode("utf-8") or "null")
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = None
        if isinstance(body, dict) and body.get("code"):
            error = TransportError.from_error_object(_ERROR_JSON.validate_python(body))
            if error.retryable is None:
                error.retryable = status_code in _RETRYABLE_STATUS
            return error
        code = _HTTP_ERROR_STATUS.get(status_code, "internal")
        return TransportError(
            code,
            f"HTTP {status_code}",
            retryable=status_code in _RETRYABLE_STATUS,
        )
