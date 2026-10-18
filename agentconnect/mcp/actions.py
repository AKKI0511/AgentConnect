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
from typing import TYPE_CHECKING, Optional

from agentconnect.core.base import JsonObject, JsonValue
from agentconnect.core.directory import (
    FindResult,
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
    HistoryView,
    RequestSendRequest,
    EventSendRequest,
    TellView,
    TicketedSendResult,
    SendResult,
    GetResultRequest,
    TellToolRequest,
    history_view,
    tell_view,
)
from agentconnect.core.primitives import CollectMode
from agentconnect.core.ticket import TicketView, ticket_view
from agentconnect.mcp.ids import message_id_for_tool, thread_id_for_tool
from agentconnect.team.errors import TeamError

KEYED_ID_CONFLICT_MESSAGE = (
    "The same idempotency_key was used with different arguments. "
    "Retry the identical call unchanged, or use a new key only for new work. "
    "Do not drop the key after an uncertain accept; that can duplicate work."
)


if TYPE_CHECKING:
    from agentconnect.team import Team


def deadline_rfc3339(seconds: float) -> str:
    """Return a future UTC timestamp the Runtime will accept."""
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _recover_generated_ask(
    runtime: Team,
    session_token: str,
    message_id: str,
    supplied_thread: Optional[str],
) -> Optional[tuple[str, str]]:
    """Return stored Thread id and deadline for an accepted keyed ask."""
    try:
        ticket = await runtime.get_result(session_token, message_id)
    except TeamError as exc:
        if exc.code == "not_found":
            return None
        raise
    thread_id = supplied_thread or ticket.thread_id
    deadline = ticket.deadline
    if thread_id is None:
        return None
    return thread_id, deadline


async def find_action(
    runtime: Team, session_token: str, request: FindRequest
) -> FindResult:
    """Run Directory ``find`` as ``session_token``."""
    return await runtime.find(session_token, request.query, limit=request.limit)


async def get_profiles_action(
    runtime: Team, session_token: str, request: GetProfilesRequest
) -> GetProfilesResult:
    """Return selected teammate Profiles, with per-item errors."""
    parsed = request
    items: list[ProfileFound | ProfileMiss] = []
    for requested in parsed.unique_requested():
        try:
            entry = await runtime.get_profile(session_token, requested)
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
    return GetProfilesResult(items=items)


async def ask_action(
    runtime: Team, session_token: str, caller_address: str, request: AskToolRequest
) -> TicketView:
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
    parsed = request
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
    if not isinstance(result, TicketedSendResult):
        raise TeamError("internal", "ask did not return a Ticket")
    return ticket_view(result.ticket)


async def _send_ask(
    runtime: Team,
    session_token: str,
    *,
    message_id: str,
    recipient: str,
    content: JsonValue,
    collect: CollectMode,
    deadline: Optional[str],
    thread_id: str,
    reraise_conflict: bool = False,
    idempotency_key: Optional[str] = None,
) -> SendResult | None:
    try:
        body: JsonObject = {
            "id": message_id,
            "recipient": recipient,
            "kind": "request",
            "content": content,
            "collect": collect,
            "thread_id": thread_id,
        }
        if deadline is not None:
            body["deadline"] = deadline
        return await runtime.send(
            session_token, RequestSendRequest.model_validate(body)
        )
    except TeamError as exc:
        if exc.code == "id_conflict" and not reraise_conflict:
            return None
        if exc.code == "id_conflict" and idempotency_key:
            raise _keyed_id_conflict(idempotency_key) from exc
        raise


async def tell_action(
    runtime: Team, session_token: str, caller_address: str, request: TellToolRequest
) -> TellView:
    """Send without expecting a reply. Returns ``TellView``.

    A keyed retry with the same arguments returns the original accepted
    send. Changed keyed arguments raise ``id_conflict``.
    """
    parsed = request
    arg_thread = parsed.thread_id
    key = parsed.idempotency_key
    message_id = message_id_for_tool(
        "tell",
        caller_address,
        idempotency_key=key,
    )
    body: JsonObject = {
        "id": message_id,
        "recipient": parsed.recipient,
        "kind": "event",
        "content": parsed.content,
    }
    if arg_thread is not None:
        body["thread_id"] = arg_thread
    try:
        sent = await runtime.send(session_token, EventSendRequest.model_validate(body))
    except TeamError as exc:
        if exc.code == "id_conflict" and key:
            raise _keyed_id_conflict(key) from exc
        raise
    if not isinstance(sent, AcceptedSendResult):
        raise TeamError("internal", "tell did not return an accepted event")
    return tell_view(sent)


def _keyed_id_conflict(key: str | None = None) -> TeamError:
    """Return tool-facing ``id_conflict`` that names ``idempotency_key``."""
    details: JsonObject = {"argument": "idempotency_key"}
    if key:
        details["idempotency_key"] = True
    return TeamError("id_conflict", KEYED_ID_CONFLICT_MESSAGE, details=details)


async def get_result_action(
    runtime: Team, session_token: str, request: GetResultRequest
) -> TicketView:
    """Return the current TicketView owned by this Membership."""
    parsed = request
    ticket = await runtime.get_result(session_token, parsed.ticket_id)
    return ticket_view(ticket)


async def get_history_action(
    runtime: Team, session_token: str, request: GetHistoryRequest
) -> HistoryView:
    """Return one page of retained Thread history."""
    parsed = request
    raw = await runtime.get_history(
        session_token,
        parsed.thread_id,
        before=parsed.before,
        limit=50 if parsed.limit is None else parsed.limit,
    )
    return history_view(raw)
