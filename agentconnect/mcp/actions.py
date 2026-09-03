"""Runtime operations behind the five AgentConnect MCP tools.

These functions take an already-resolved Session token. The MCP server
resolves the caller, then calls here. Session-bound callables in
``agentconnect.agent.tools`` use the same send and wait rules.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Protocol

from agentconnect.core.base import dump_public
from agentconnect.mcp.ids import message_id_for_tool
from agentconnect.team.errors import TeamError


class TeamRuntime(Protocol):
    """Runtime operations the MCP door needs. ``Team`` satisfies this."""

    name: str

    async def ensure_operator_session(self) -> str:
        """Return a live Session token for the loopback operator."""

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept one request or event."""

    async def find(
        self,
        session_token: str,
        query: str,
        *,
        limit: int | None = None,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Search this Team's Directory."""

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return a Ticket this Session's Membership owns."""

    async def get_history(
        self,
        session_token: str,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history."""

    async def roster(self) -> dict[str, Any]:
        """Return every Membership as a DirectoryEntry list."""

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Refresh Session expiry."""

    async def caller_address(self, session_token: str) -> str:
        """Return the qualified Address stamped on this Session."""


def deadline_rfc3339(seconds: float) -> str:
    """Return a future UTC timestamp the Runtime will accept."""
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def bearer_token(headers: Mapping[str, str] | None) -> Optional[str]:
    """Return the Bearer token from ``Authorization``, or None if absent."""
    if not headers:
        return None
    value: str | None = None
    for key, item in headers.items():
        if str(key).lower() == "authorization":
            value = str(item)
            break
    if not value:
        return None
    if not value.lower().startswith("bearer "):
        raise TeamError("unauthorized", "Session is missing or invalid")
    token = value.split(" ", 1)[1].strip()
    if not token:
        raise TeamError("unauthorized", "Session is missing or invalid")
    return token


async def resolve_session(
    runtime: TeamRuntime,
    headers: Mapping[str, str] | None,
) -> str:
    """Return the Session token for this MCP call.

    A Bearer token is verified by a heartbeat. A missing header uses the
    loopback operator Session.
    """
    token = bearer_token(headers)
    if token is None:
        return await runtime.ensure_operator_session()
    await runtime.heartbeat(token)
    return token


def _int_in_range(
    value: Any, *, name: str, minimum: int, maximum: int, default: int | None = None
) -> int:
    if value is None:
        if default is None:
            raise ValueError(f"{name} is required")
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def _optional_uuid(value: Any, *, name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a UUID")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a UUID") from exc
    return value


def _require_uuid(value: Any, *, name: str) -> str:
    found = _optional_uuid(value, name=name)
    if found is None:
        raise ValueError(f"{name} is required")
    return found


def _optional_key(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not (1 <= len(value) <= 200):
        raise ValueError("idempotency_key must be 1 to 200 characters")
    return value


async def wait_for_ticket(
    runtime: TeamRuntime,
    session_token: str,
    ticket_id: str,
    wait_seconds: float,
) -> dict[str, Any]:
    """Poll ``get_result`` until the Ticket is terminal or ``wait_seconds`` elapses."""
    if wait_seconds <= 0:
        return dump_public(await runtime.get_result(session_token, ticket_id))
    deadline = time.monotonic() + float(wait_seconds)
    while True:
        ticket = dump_public(await runtime.get_result(session_token, ticket_id))
        if ticket.get("state") != "open":
            return ticket
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ticket
        await asyncio.sleep(min(0.05, remaining))


async def find_action(
    runtime: TeamRuntime,
    session_token: str,
    query: str,
    *,
    limit: int | None = None,
    detail: str = "summary",
) -> dict[str, Any]:
    """Run Directory ``find`` as ``session_token``."""
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError("query must be 1 to 1000 non-whitespace characters")
    cap: int | None
    if limit is None:
        cap = None
    else:
        cap = _int_in_range(limit, name="limit", minimum=1, maximum=100)
    if detail not in {"summary", "full"}:
        raise ValueError("detail must be summary or full")
    return dump_public(
        await runtime.find(session_token, query, limit=cap, detail=detail)
    )


async def ask_action(
    runtime: TeamRuntime,
    session_token: str,
    caller_address: str,
    recipient: str,
    content: Any,
    *,
    deadline_seconds: int,
    wait_seconds: int = 0,
    thread_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    """Send a reply-expected request with ``collect=ticket``.

    Returns the current Ticket. ``wait_seconds`` may hold for a terminal
    state. An omitted ``thread_id`` is minted for the send.
    """
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient is required")
    deadline_s = _int_in_range(
        deadline_seconds, name="deadline_seconds", minimum=1, maximum=86400
    )
    wait_s = _int_in_range(
        wait_seconds, name="wait_seconds", minimum=0, maximum=30, default=0
    )
    arg_thread = _optional_uuid(thread_id, name="thread_id")
    key = _optional_key(idempotency_key)
    message_id = message_id_for_tool(
        "ask",
        caller_address,
        idempotency_key=key,
    )
    send_thread = arg_thread or str(uuid.uuid4())
    try:
        result = dump_public(
            await runtime.send(
                session_token,
                {
                    "id": message_id,
                    "recipient": recipient,
                    "kind": "request",
                    "content": content,
                    "collect": "ticket",
                    "deadline": deadline_rfc3339(deadline_s),
                    "thread_id": send_thread,
                },
            )
        )
    except TeamError as exc:
        if exc.code == "id_conflict" and key:
            return await wait_for_ticket(runtime, session_token, message_id, wait_s)
        raise
    ticket = result.get("ticket")
    if not isinstance(ticket, dict):
        raise TeamError("internal", "ask did not return a Ticket")
    ticket_id = ticket.get("id")
    if not isinstance(ticket_id, str):
        raise TeamError("internal", "ask did not return a Ticket")
    return await wait_for_ticket(runtime, session_token, ticket_id, wait_s)


async def tell_action(
    runtime: TeamRuntime,
    session_token: str,
    caller_address: str,
    recipient: str,
    content: Any,
    *,
    thread_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    """Send an event. Returns ``AcceptedSendResult``."""
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient is required")
    arg_thread = _optional_uuid(thread_id, name="thread_id")
    key = _optional_key(idempotency_key)
    message_id = message_id_for_tool(
        "tell",
        caller_address,
        idempotency_key=key,
    )
    body: dict[str, Any] = {
        "id": message_id,
        "recipient": recipient,
        "kind": "event",
        "content": content,
    }
    if arg_thread is not None:
        body["thread_id"] = arg_thread
    try:
        return dump_public(await runtime.send(session_token, body))
    except TeamError as exc:
        if exc.code == "id_conflict" and key:
            return {
                "status": "accepted",
                "message": {"id": message_id, "kind": "event", "content": content},
            }
        raise


async def get_result_action(
    runtime: TeamRuntime, session_token: str, ticket_id: str
) -> dict[str, Any]:
    """Return the current Ticket owned by this Session."""
    return dump_public(
        await runtime.get_result(
            session_token, _require_uuid(ticket_id, name="ticket_id")
        )
    )


async def get_history_action(
    runtime: TeamRuntime,
    session_token: str,
    thread_id: str,
    *,
    before: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return one page of retained Thread history."""
    thread = _require_uuid(thread_id, name="thread_id")
    before_id = _optional_uuid(before, name="before")
    cap = _int_in_range(limit, name="limit", minimum=1, maximum=200, default=50)
    return dump_public(
        await runtime.get_history(session_token, thread, before=before_id, limit=cap)
    )
