"""Runtime operations behind the five AgentConnect MCP tools.

These functions take an already-resolved Session token. The MCP server
resolves the caller, then calls here. Session-bound callables in
``agentconnect.agent.tools`` use the same send and wait rules.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Protocol

from agentconnect.core.base import dump_public, parse_schema
from agentconnect.core.directory import FindRequest
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
)
from agentconnect.mcp.ids import message_id_for_tool, thread_id_for_tool
from agentconnect.team.errors import TeamError
from agentconnect.team.session_auth import session_token_for_request


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
        """Return a Ticket this Membership owns."""

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

    async def require_live_session(self, session_token: str) -> str:
        """Return ``session_token`` if the Session is live. Does not renew it."""

    async def caller_address(self, session_token: str) -> str:
        """Return the qualified Address stamped on this Session."""


def deadline_rfc3339(seconds: float) -> str:
    """Return a future UTC timestamp the Runtime will accept."""
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def resolve_session(
    runtime: TeamRuntime,
    headers: Mapping[str, str] | None,
    *,
    peer_host: str | None = None,
    in_process: bool = False,
) -> str:
    """Return the Session token for this MCP call.

    A Bearer token is checked without renewing expiry. A missing header
    uses the operator Session only when ``in_process`` is True or the
    HTTP peer is an explicitly trusted loopback path.
    """
    return await session_token_for_request(
        runtime,
        headers,
        peer_host=peer_host,
        in_process=in_process,
    )


async def _recover_generated_ask(
    runtime: TeamRuntime,
    session_token: str,
    message_id: str,
    supplied_thread: Optional[str],
) -> Optional[tuple[str, str]]:
    """Return stored Thread id and deadline for an accepted keyed ask."""
    try:
        ticket = dump_public(await runtime.get_result(session_token, message_id))
    except TeamError as exc:
        if exc.code == "not_found":
            return None
        raise
    thread_id = supplied_thread or ticket.get("thread_id")
    deadline = ticket.get("deadline")
    if not isinstance(thread_id, str) or not isinstance(deadline, str):
        return None
    return thread_id, deadline


async def find_action(
    runtime: TeamRuntime,
    session_token: str,
    query: str,
    *,
    limit: int | None = None,
    detail: str = "summary",
) -> dict[str, Any]:
    """Run Directory ``find`` as ``session_token``."""
    payload: dict[str, Any] = {"query": query, "detail": detail}
    if limit is not None:
        payload["limit"] = limit
    parsed = parse_schema(FindRequest, payload)
    return dump_public(
        await runtime.find(
            session_token,
            parsed.query,
            limit=parsed.limit,
            detail=parsed.detail,
        )
    )


async def ask_action(
    runtime: TeamRuntime,
    session_token: str,
    caller_address: str,
    recipient: str,
    content: Any,
    *,
    deadline_seconds: int,
    collect: str = "wait",
    thread_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    """Send a reply-expected request and return the current Ticket.

    ``collect`` matches Runtime ``send``. The wait hold may return an
    ``open`` Ticket; call ``get_result`` for the terminal state.
    An omitted ``thread_id`` is minted for the send. A keyed retry
    recovers the original generated Thread and deadline.

        ticket = await ask_action(
            team, token, "researcher@content-squad",
            "writer", "draft this", deadline_seconds=30,
        )
        ticket["id"]
    """
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient is required")
    payload: dict[str, Any] = {
        "recipient": recipient,
        "content": content,
        "deadline_seconds": deadline_seconds,
        "collect": collect,
    }
    if thread_id is not None:
        payload["thread_id"] = thread_id
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    parsed = parse_schema(AskToolRequest, payload)
    deadline_s = parsed.deadline_seconds
    collect = parsed.collect
    if collect not in {"wait", "ticket"}:
        raise ValueError("collect must be wait or ticket")
    arg_thread = parsed.thread_id
    key = parsed.idempotency_key
    message_id = message_id_for_tool(
        "ask",
        caller_address,
        idempotency_key=key,
    )
    if arg_thread is not None:
        send_thread = arg_thread
    elif key:
        send_thread = thread_id_for_tool("ask", caller_address, idempotency_key=key)
    else:
        send_thread = str(uuid.uuid4())
    deadline = deadline_rfc3339(deadline_s)
    recovered_before = False
    if key:
        recovered = await _recover_generated_ask(
            runtime, session_token, message_id, arg_thread
        )
        if recovered is not None:
            send_thread, deadline = recovered
            recovered_before = True
    result = await _send_ask(
        runtime,
        session_token,
        message_id=message_id,
        recipient=parsed.recipient,
        content=parsed.content,
        collect=collect,
        deadline=deadline,
        thread_id=send_thread,
        reraise_conflict=recovered_before or not key,
    )
    if result is None and key:
        recovered = await _recover_generated_ask(
            runtime, session_token, message_id, arg_thread
        )
        if recovered is None:
            raise TeamError(
                "id_conflict", "Message id is already used with different data"
            )
        send_thread, deadline = recovered
        result = await _send_ask(
            runtime,
            session_token,
            message_id=message_id,
            recipient=parsed.recipient,
            content=parsed.content,
            collect=collect,
            deadline=deadline,
            thread_id=send_thread,
            reraise_conflict=True,
        )
    if result is None:
        raise TeamError("id_conflict", "Message id is already used with different data")
    ticket = result.get("ticket")
    if not isinstance(ticket, dict):
        raise TeamError("internal", "ask did not return a Ticket")
    return ticket


async def _send_ask(
    runtime: TeamRuntime,
    session_token: str,
    *,
    message_id: str,
    recipient: str,
    content: Any,
    collect: str,
    deadline: str,
    thread_id: str,
    reraise_conflict: bool = False,
) -> dict[str, Any] | None:
    try:
        return dump_public(
            await runtime.send(
                session_token,
                {
                    "id": message_id,
                    "recipient": recipient,
                    "kind": "request",
                    "content": content,
                    "collect": collect,
                    "deadline": deadline,
                    "thread_id": thread_id,
                },
            )
        )
    except TeamError as exc:
        if exc.code == "id_conflict" and not reraise_conflict:
            return None
        raise


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
    """Send an event. Returns ``AcceptedSendResult``.

    A keyed retry with the same arguments returns the original accepted
    event. Changed keyed arguments raise ``id_conflict``.
    """
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient is required")
    payload: dict[str, Any] = {"recipient": recipient, "content": content}
    if thread_id is not None:
        payload["thread_id"] = thread_id
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    parsed = parse_schema(TellToolRequest, payload)
    arg_thread = parsed.thread_id
    key = parsed.idempotency_key
    message_id = message_id_for_tool(
        "tell",
        caller_address,
        idempotency_key=key,
    )
    body: dict[str, Any] = {
        "id": message_id,
        "recipient": parsed.recipient,
        "kind": "event",
        "content": parsed.content,
    }
    if arg_thread is not None:
        body["thread_id"] = arg_thread
    return dump_public(await runtime.send(session_token, body))


async def get_result_action(
    runtime: TeamRuntime, session_token: str, ticket_id: str
) -> dict[str, Any]:
    """Return the current Ticket owned by this Membership."""
    parsed = parse_schema(GetResultRequest, {"ticket_id": ticket_id})
    return dump_public(await runtime.get_result(session_token, parsed.ticket_id))


async def get_history_action(
    runtime: TeamRuntime,
    session_token: str,
    thread_id: str,
    *,
    before: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return one page of retained Thread history."""
    payload: dict[str, Any] = {"thread_id": thread_id, "limit": limit}
    if before is not None:
        payload["before"] = before
    parsed = parse_schema(GetHistoryRequest, payload)
    return dump_public(
        await runtime.get_history(
            session_token,
            parsed.thread_id,
            before=parsed.before,
            limit=50 if parsed.limit is None else parsed.limit,
        )
    )
