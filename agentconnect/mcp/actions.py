"""Runtime operations behind the AgentConnect MCP tools.

These functions take an already-resolved Session token. The MCP server
resolves the caller, then calls here. Session-bound callables in
``agentconnect.agent.tools`` use the same send and wait rules. Model-facing
``ask`` and ``get_result`` return TicketView JSON. ``tell``, ``get_profiles``,
and ``get_history`` return lean views.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Protocol

from agentconnect.core.base import dump_public, parse_schema
from agentconnect.core.directory import (
    DirectoryEntry,
    FindRequest,
    GetProfilesRequest,
    GetProfilesResult,
    ProfileFound,
    ProfileMiss,
)
from agentconnect.core.error import ErrorObject
from agentconnect.core.operations import (
    AcceptedSendResult,
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
    history_view,
    parse_history_result,
    parse_send_result,
    tell_view,
)
from agentconnect.core.primitives import CollectMode
from agentconnect.core.ticket import parse_ticket, ticket_view
from agentconnect.mcp.ids import message_id_for_tool, thread_id_for_tool
from agentconnect.team.errors import TeamError
from agentconnect.team.session_auth import session_token_for_request

KEYED_ID_CONFLICT_MESSAGE = (
    "The same idempotency_key was used with different arguments. "
    "Retry the identical call unchanged, or use a new key only for new work. "
    "Do not drop the key after an uncertain accept; that can duplicate work."
)


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
    ) -> dict[str, Any]:
        """Search this Team's Directory."""

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry."""

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
) -> dict[str, Any]:
    """Run Directory ``find`` as ``session_token``."""
    payload: dict[str, Any] = {"query": query}
    if limit is not None:
        payload["limit"] = limit
    parsed = parse_schema(FindRequest, payload)
    return dump_public(
        await runtime.find(
            session_token,
            parsed.query,
            limit=parsed.limit,
        )
    )


async def get_profiles_action(
    runtime: TeamRuntime, session_token: str, addresses: list[str]
) -> dict[str, Any]:
    """Return selected teammate Profiles, with per-item errors."""
    parsed = parse_schema(GetProfilesRequest, {"addresses": addresses})
    items: list[ProfileFound | ProfileMiss] = []
    for requested in parsed.unique_requested():
        try:
            entry = await runtime.get_profile(session_token, requested)
            if not isinstance(entry, DirectoryEntry):
                entry = DirectoryEntry.model_validate(entry)
            items.append(
                ProfileFound(
                    status="ok",
                    address=entry.address,
                    profile=entry.profile,
                )
            )
        except TeamError as exc:
            if exc.code == "unauthorized":
                raise
            if exc.code not in {"not_found", "forbidden", "address_outside_team"}:
                raise
            items.append(
                ProfileMiss(
                    status="error",
                    address=requested,
                    error=ErrorObject.model_validate(exc.to_error_object()),
                )
            )
    return dump_public(GetProfilesResult(items=items))


async def ask_action(
    runtime: TeamRuntime,
    session_token: str,
    caller_address: str,
    recipient: str,
    content: Any,
    *,
    deadline_seconds: Optional[int] = None,
    collect: CollectMode = "wait",
    thread_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    """Send a reply-expected request and return the current TicketView.

    ``collect`` matches Runtime ``send``. The wait hold may return an
    ``open`` TicketView; call ``get_result`` for the terminal state.
    An omitted ``thread_id`` is minted for the send. A keyed retry
    recovers the original generated Thread. An omitted deadline inherits
    a request parent or the Runtime work lifetime.

        ticket = await ask_action(
            team, token, "researcher@content-squad",
            "writer", "draft this",
        )
        ticket["ticket_id"]
    """
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient is required")
    payload: dict[str, Any] = {
        "recipient": recipient,
        "content": content,
        "collect": collect,
    }
    if deadline_seconds is not None:
        payload["deadline_seconds"] = deadline_seconds
    if thread_id is not None:
        payload["thread_id"] = thread_id
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    parsed = parse_schema(AskToolRequest, payload)
    deadline_s = parsed.deadline_seconds
    collect = parsed.collect
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
    deadline = deadline_rfc3339(deadline_s) if deadline_s is not None else None
    recovered_before = False
    if key:
        recovered = await _recover_generated_ask(
            runtime, session_token, message_id, arg_thread
        )
        if recovered is not None:
            send_thread, recovered_deadline = recovered
            recovered_before = True
            if deadline_s is not None:
                deadline = recovered_deadline
            else:
                deadline = None
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
        idempotency_key=key,
    )
    if result is None and key:
        recovered = await _recover_generated_ask(
            runtime, session_token, message_id, arg_thread
        )
        if recovered is None:
            raise _keyed_id_conflict(key)
        send_thread, recovered_deadline = recovered
        if deadline_s is not None:
            deadline = recovered_deadline
        else:
            deadline = None
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
            idempotency_key=key,
        )
    if result is None:
        raise _keyed_id_conflict(key)
    ticket = result.get("ticket")
    if not isinstance(ticket, dict):
        raise TeamError("internal", "ask did not return a Ticket")
    return dump_public(ticket_view(parse_ticket(ticket)))


async def _send_ask(
    runtime: TeamRuntime,
    session_token: str,
    *,
    message_id: str,
    recipient: str,
    content: Any,
    collect: CollectMode,
    deadline: Optional[str],
    thread_id: str,
    reraise_conflict: bool = False,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any] | None:
    try:
        body: dict[str, Any] = {
            "id": message_id,
            "recipient": recipient,
            "kind": "request",
            "content": content,
            "collect": collect,
            "thread_id": thread_id,
        }
        if deadline is not None:
            body["deadline"] = deadline
        return dump_public(await runtime.send(session_token, body))
    except TeamError as exc:
        if exc.code == "id_conflict" and not reraise_conflict:
            return None
        if exc.code == "id_conflict" and idempotency_key:
            raise _keyed_id_conflict(idempotency_key) from exc
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
    """Send without expecting a reply. Returns ``TellView``.

    A keyed retry with the same arguments returns the original accepted
    send. Changed keyed arguments raise ``id_conflict``.
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
    try:
        sent = parse_send_result(await runtime.send(session_token, body))
    except TeamError as exc:
        if exc.code == "id_conflict" and key:
            raise _keyed_id_conflict(key) from exc
        raise
    if not isinstance(sent, AcceptedSendResult):
        raise TeamError("internal", "tell did not return an accepted event")
    return dump_public(tell_view(sent))


def _keyed_id_conflict(key: str | None = None) -> TeamError:
    """Return tool-facing ``id_conflict`` that names ``idempotency_key``."""
    details = {"argument": "idempotency_key"}
    if key:
        details["idempotency_key"] = True
    return TeamError("id_conflict", KEYED_ID_CONFLICT_MESSAGE, details=details)


async def get_result_action(
    runtime: TeamRuntime, session_token: str, ticket_id: str
) -> dict[str, Any]:
    """Return the current TicketView owned by this Membership."""
    parsed = parse_schema(GetResultRequest, {"ticket_id": ticket_id})
    ticket = parse_ticket(await runtime.get_result(session_token, parsed.ticket_id))
    return dump_public(ticket_view(ticket))


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
    raw = await runtime.get_history(
        session_token,
        parsed.thread_id,
        before=parsed.before,
        limit=50 if parsed.limit is None else parsed.limit,
    )
    return dump_public(history_view(parse_history_result(raw)))
