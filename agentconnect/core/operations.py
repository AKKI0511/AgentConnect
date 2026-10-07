"""Runtime operation requests and results from the public schema."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError

from agentconnect.core.base import (
    JsonFloat,
    JsonInt,
    JsonObject,
    JsonValue,
    SchemaModel,
    parse_schema,
    validation_message,
)
from agentconnect.core.directory import DirectoryEntry, FindRequest
from agentconnect.core.error import ErrorObject
from agentconnect.core.message import (
    Delivery,
    ErrorMessage,
    EventMessage,
    Message,
    RequestMessage,
    ResponseMessage,
    parse_delivery,
    parse_message,
)
from agentconnect.core.primitives import (
    Address,
    AgentDid,
    AgentName,
    CollectMode,
    DeliveryHistoryForm,
    PersistenceMode,
    QualifiedAddress,
    SessionToken,
    SpecVersion,
    TeamName,
    Timestamp,
    TraceEventType,
    Uuid,
)
from agentconnect.core.profile import AgentProfile
from agentconnect.core.ticket import (
    CompletedTicket,
    DeclinedTicket,
    FailedTicket,
    Ticket,
    TicketViewError,
    parse_ticket,
)

__all__ = [
    "JoinChallenge",
    "JoinRequest",
    "RuntimeLimits",
    "JoinResult",
    "HeartbeatResult",
    "SendBase",
    "RequestSendRequest",
    "EventSendRequest",
    "SendRequest",
    "AcceptedSendResult",
    "TellView",
    "TicketedSendResult",
    "SendResult",
    "LeaseRequest",
    "LeaseResult",
    "RenewRequest",
    "RenewResult",
    "CompleteRequest",
    "CompleteResult",
    "ReplyBase",
    "ReplySuccessRequest",
    "ReplyFailureRequest",
    "ReplyRequest",
    "ReplyResult",
    "GetResultRequest",
    "GetHistoryRequest",
    "HistoryResult",
    "HistoryTurnBase",
    "HistoryRequestTurn",
    "HistoryEventTurn",
    "HistoryResponseTurn",
    "HistoryErrorTurn",
    "HistoryTurn",
    "HistoryView",
    "AskToolRequest",
    "TellToolRequest",
    "TeamRoster",
    "TraceEvent",
    "TraceResult",
    "StatusAgent",
    "StatusPrincipal",
    "StatusMember",
    "StatusResult",
    "IssueJoinTokenRequest",
    "JoinTokenIssued",
    "RevokeJoinTokenRequest",
    "RuntimeEvent",
    "ToolErrorResult",
    "parse_join_request",
    "parse_join_result",
    "parse_send_request",
    "parse_send_result",
    "parse_reply_request",
    "parse_lease_request",
    "parse_lease_result",
    "parse_renew_request",
    "parse_complete_request",
    "parse_history_result",
    "parse_find_request",
    "tell_view",
    "history_view",
    "parse_issue_join_token_request",
    "parse_revoke_join_token_request",
]


class JoinChallenge(SchemaModel):
    """Short-lived challenge used to prove Agent DID control."""

    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{22,64}$")
    audience: str = Field(
        pattern=r"^agentconnect:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
    )
    expires_at: Timestamp


class JoinRequest(SchemaModel):
    """Input that creates or reconnects a Membership and opens one Instance.

    ``spec_version`` is required on the wire. ``Team.join`` fills it when
    you pass kwargs. ``delivery_history="ids"`` puts earlier Message ids
    on each Delivery instead of Message bodies. Omit it to receive bodies.
    """

    spec_version: SpecVersion
    name: AgentName
    agent_did: AgentDid
    profile: AgentProfile
    instance_id: Optional[Uuid] = None
    max_in_flight: Optional[JsonInt] = Field(default=None, ge=1, le=100)
    join_token: Optional[str] = Field(default=None, min_length=1)
    identity_proof: Optional[str] = Field(default=None, min_length=1)
    delivery_history: Optional[DeliveryHistoryForm] = None


class RuntimeLimits(SchemaModel):
    """Fixed operational limits a Runtime reports at join.

    ``max_message_bytes`` bounds ``send``, ``reply``, and HTTP JSON
    ingress. ``max_held_waits`` caps concurrent ``collect=wait`` sends
    per Membership. ``max_mailbox_depth`` caps queued plus leased
    Mailbox items. ``max_open_tickets`` caps open Tickets one
    Membership may hold as requester. ``work_lifetime_seconds`` is the
    finite cutoff stamped on a new request whose send omitted
    ``deadline`` and that has no request parent to inherit from.
    ``max_deadline_seconds`` is the farthest a new request deadline may
    be. ``replay_horizon_seconds`` is how long an identical retry still
    returns the original result after the obligation ends, taken as the
    later of that interval after close and the Ticket deadline for a
    request. After the window, reuse of the id is new work only when no
    remaining owner names it.
    ``max_retained_bytes`` caps retained Message-body storage.

        result.limits.max_message_bytes
        result.limits.replay_horizon_seconds
    """

    max_message_bytes: JsonInt = Field(ge=1)
    max_mailbox_depth: JsonInt = Field(ge=1)
    delivery_history_limit: JsonInt = Field(ge=0)
    wait_hold_seconds: JsonFloat = Field(ge=0)
    max_held_waits: JsonInt = Field(ge=0)
    work_lifetime_seconds: JsonFloat = Field(ge=1)
    max_deadline_seconds: JsonFloat = Field(ge=1)
    max_open_tickets: JsonInt = Field(ge=1)
    replay_horizon_seconds: JsonFloat = Field(ge=1)
    max_retained_bytes: JsonInt = Field(ge=1)


class JoinResult(SchemaModel):
    """Result of a successful join."""

    session_token: SessionToken
    session_expires_at: Timestamp
    address: QualifiedAddress
    team_name: TeamName
    agent_did: AgentDid
    instance_id: Uuid
    persistence: PersistenceMode
    limits: RuntimeLimits
    spec_version: SpecVersion


class HeartbeatResult(SchemaModel):
    """Result of a successful Session heartbeat."""

    session_expires_at: Timestamp


class SendBase(SchemaModel):
    """Fields shared by request and event sends.

    ``id`` is Client-generated and becomes the accepted Message id.
    """

    id: Uuid
    recipient: Address
    content: JsonValue
    thread_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None
    metadata: Optional[JsonObject] = None


class RequestSendRequest(SendBase):
    """Send a request. Always opens a Ticket.

    ``collect`` is ``wait`` or ``ticket``. ``deadline`` may be omitted;
    the Runtime stamps the effective cutoff on the accepted Message.
    Fire-and-forget work is :class:`EventSendRequest`.

        RequestSendRequest(
            id=message_id,
            recipient="writer",
            kind="request",
            content={"task": "draft this"},
            collect="ticket",
            deadline="2026-08-18T15:10:00Z",
        )
    """

    kind: Literal["request"]
    collect: CollectMode
    deadline: Optional[Timestamp] = None


class EventSendRequest(SendBase):
    """Send information without a reply."""

    kind: Literal["event"]


SendRequest = Union[RequestSendRequest, EventSendRequest]


class AcceptedSendResult(SchemaModel):
    """Result for an event."""

    status: Literal["accepted"]
    message: EventMessage


class TellView(SchemaModel):
    """Model-facing ``tell`` result.

    ``status: accepted`` means the Runtime queued the event, not that
    the recipient finished processing. No Ticket is created.
    """

    status: Literal["accepted"]
    thread_id: Optional[Uuid] = None


class TicketedSendResult(SchemaModel):
    """Result for a request.

    ``ticket`` is the current Ticket. Immediate ``collect=ticket`` and an
    elapsed ``wait`` hold both use this wrapper. ``state`` may be ``open``
    or terminal.

        result.ticket.state
        result.ticket.id
    """

    status: Literal["ticketed"]
    message: RequestMessage
    ticket: Ticket


SendResult = Annotated[
    Union[AcceptedSendResult, TicketedSendResult],
    Field(discriminator="status"),
]


class LeaseRequest(SchemaModel):
    """Input to pull available work."""

    max_items: Optional[JsonInt] = Field(default=None, ge=1, le=100)


class LeaseResult(SchemaModel):
    """Deliveries currently leased to the Session."""

    deliveries: list[Delivery]


class RenewRequest(SchemaModel):
    """Input to extend one active Delivery lease.

    RenewRequest(lease_id=delivery.lease_id)
    """

    lease_id: Uuid


class RenewResult(SchemaModel):
    """Result of a successful ``renew``.

    result.lease_expires_at
    """

    lease_id: Uuid
    lease_expires_at: Timestamp


class CompleteRequest(SchemaModel):
    """Finish one Delivery without a response.

    An event just ends. A request is declined.
    """

    lease_id: Uuid


class CompleteResult(SchemaModel):
    """Result of ``complete``."""

    ticket: Optional[DeclinedTicket] = None


class ReplyBase(SchemaModel):
    """Fields shared by successful and failed replies.

    Replay equality includes ``id``, the target request Message id, and
    the outcome data. ``lease_id`` authorizes the attempt.
    """

    id: Uuid
    lease_id: Uuid


class ReplySuccessRequest(ReplyBase):
    """Complete a Delivery with successful content."""

    outcome: Literal["completed"]
    content: JsonValue


class ReplyFailureRequest(ReplyBase):
    """Complete a Delivery with a safe error."""

    outcome: Literal["failed"]
    error: ErrorObject


ReplyRequest = Annotated[
    Union[ReplySuccessRequest, ReplyFailureRequest],
    Field(discriminator="outcome"),
]


class ReplyResult(SchemaModel):
    """Result of an accepted reply."""

    ticket: Union[CompletedTicket, FailedTicket]


class GetResultRequest(SchemaModel):
    """Collect the current saved request result."""

    ticket_id: Uuid = Field(
        description=(
            "ticket_id from ask, equal to the request Message id. Repeat "
            "while state is open. Ending a wait does not cancel work."
        )
    )


class GetHistoryRequest(SchemaModel):
    """Thread history lookup.

    Pages are newest-first, but Messages inside a page are oldest to
    newest by ``seq``. Pass ``next_before`` from the previous page as
    ``before``. Stop when ``has_more`` is false.
    """

    thread_id: Uuid = Field(
        description=(
            "Conversation id from a saved request result or Message. Only a "
            "participant may read it."
        )
    )
    before: Optional[Uuid] = Field(
        default=None,
        description=(
            "Return Messages older than this id. Omit for the newest page. "
            "Prefer next_before from the previous page over picking an id."
        ),
    )
    limit: Optional[JsonInt] = Field(
        default=None,
        ge=1,
        le=200,
        description="Page size from 1 to 200. Defaults to 50.",
    )


class HistoryResult(SchemaModel):
    """One page of retained Thread history.

    ``messages`` are ordered by ``seq`` ascending. The newest page is
    returned first. When ``has_more`` is true, pass ``next_before`` as
    the next ``before``.
    """

    messages: list[Message]
    has_more: bool
    next_before: Optional[Uuid] = None


class HistoryTurnBase(SchemaModel):
    """Fields shared by every model-facing history turn."""

    id: Uuid
    seq: JsonInt = Field(ge=1)
    sender: QualifiedAddress
    created_at: Timestamp


class HistoryRequestTurn(HistoryTurnBase):
    """Request turn on a model-facing history page."""

    kind: Literal["request"]
    content: JsonValue


class HistoryEventTurn(HistoryTurnBase):
    """Event turn on a model-facing history page."""

    kind: Literal["event"]
    content: JsonValue


class HistoryResponseTurn(HistoryTurnBase):
    """Successful reply turn on a model-facing history page.

    ``parent_id`` is the request Message id this reply answers, the same
    value as that ask's ``ticket_id``.
    """

    kind: Literal["response"]
    parent_id: Uuid
    content: JsonValue


class HistoryErrorTurn(HistoryTurnBase):
    """Failed reply turn on a model-facing history page.

    ``parent_id`` is the request Message id this error answers, the same
    value as that ask's ``ticket_id``.
    """

    kind: Literal["error"]
    parent_id: Uuid
    error: TicketViewError


HistoryTurn = Annotated[
    Union[
        HistoryRequestTurn,
        HistoryEventTurn,
        HistoryResponseTurn,
        HistoryErrorTurn,
    ],
    Field(discriminator="kind"),
]


class HistoryView(SchemaModel):
    """Model-facing Thread history page. Same paging as ``HistoryResult``."""

    messages: list[HistoryTurn]
    has_more: bool
    next_before: Optional[Uuid] = None


class AskToolRequest(SchemaModel):
    """Send work that needs a reply.

    Returns the saved request result. ``collect=wait`` (default) may
    still return ``open``; call ``get_result`` with ``ticket_id``. A
    Thread is fixed to its original participants; another peer is
    ``forbidden``.
    """

    recipient: Address = Field(
        description="Local or same-Team qualified Address, for example writer."
    )
    content: JsonValue = Field(description="The work, as text or JSON.")
    deadline_seconds: Optional[JsonInt] = Field(
        default=None,
        ge=1,
        le=86400,
        description=(
            "Work cutoff in seconds (1–86400). Omit to inherit a request "
            "parent or the Runtime work lifetime. This is not how long ask waits."
        ),
    )
    collect: CollectMode = Field(
        default="wait",
        description=(
            "How long this ask call waits. wait (default) holds until the "
            "Ticket is terminal or the Runtime wait hold ends, then returns "
            "the current saved request result, which may still be open. "
            "ticket returns immediately. Neither cancels work. While open, "
            "call get_result; do not send a second ask."
        ),
    )
    thread_id: Optional[Uuid] = Field(
        default=None,
        description=(
            "Continue this conversation with the same recipient (a current "
            "participant). Omit to start a conversation; that is the usual "
            "path. A well-formed unused id also starts one. Another peer "
            "cannot join an existing conversation (forbidden); omit "
            "thread_id and put needed context in content."
        ),
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Stable key so a retry does not create a second request. Changing "
            "recipient, content, collect, or a supplied thread_id under the "
            "same key fails with id_conflict. Retry identical arguments, or "
            "use a new key only for new work; do not drop the key after an "
            "uncertain accept."
        ),
    )


class TellToolRequest(SchemaModel):
    """Send work that does not need a reply.

    No Ticket is created. Prefer ask when you need an answer. A Thread
    is fixed to its original participants; another peer is ``forbidden``.
    Omit ``thread_id`` for an unthreaded notice; that is the usual path.
    """

    recipient: Address = Field(
        description="Local or same-Team qualified Address, for example writer."
    )
    content: JsonValue = Field(
        description="The notice or event, as text or JSON. No Ticket is created."
    )
    thread_id: Optional[Uuid] = Field(
        default=None,
        description=(
            "Continue this conversation only with a current participant. "
            "Omit for an unthreaded notice; that is the usual path. Another "
            "peer cannot join an existing conversation (forbidden); omit "
            "thread_id and put context in content."
        ),
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Stable key so a retry does not create a second send. Changing "
            "recipient, content, or thread_id under the same key fails with "
            "id_conflict. Retry identical arguments, or use a new key only "
            "for new work; do not drop the key after an uncertain accept."
        ),
    )


class TeamRoster(SchemaModel):
    """MCP roster resource body. Agent Memberships only; principals omitted."""

    team_name: TeamName
    members: list[DirectoryEntry]


class TraceEvent(SchemaModel):
    """One recorded step of a causal operation.

    ``parent_id`` is the parent of ``message_id`` when that Message has
    one. ``get_trace`` still returns an ordered list.

        event.parent_id  # absent on a root Message
    """

    at: Timestamp
    type: TraceEventType
    trace_id: Uuid
    actor: QualifiedAddress
    message_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None
    ticket_id: Optional[Uuid] = None
    detail: JsonObject


class TraceResult(SchemaModel):
    """Result of ``get_trace``."""

    trace_id: Uuid
    events: list[TraceEvent]


class StatusAgent(SchemaModel):
    """Agent Membership row in ``status``.

    ``online`` is true when this Membership has at least one unexpired
    Session in the store.
    """

    kind: Literal["agent"]
    name: AgentName
    address: QualifiedAddress
    online: bool
    mailbox_depth: JsonInt = Field(ge=0)
    open_tickets: JsonInt = Field(ge=0)


class StatusPrincipal(SchemaModel):
    """Principal Membership row in ``status``.

    No Mailbox or Ticket counts. ``online`` is read from stored Sessions.
    """

    kind: Literal["principal"]
    name: AgentName
    address: QualifiedAddress
    online: bool


StatusMember = Annotated[
    Union[StatusAgent, StatusPrincipal],
    Field(discriminator="kind"),
]


class StatusResult(SchemaModel):
    """Result of ``status``."""

    team_name: TeamName
    persistence: PersistenceMode
    origin: Optional[str] = None
    open_tickets: JsonInt = Field(ge=0)
    members: list[StatusMember]


class IssueJoinTokenRequest(SchemaModel):
    """Operator input that creates a join token."""

    name: Optional[AgentName] = None
    agent_did: Optional[AgentDid] = None
    ttl_seconds: Optional[JsonFloat] = Field(default=None, ge=1)
    single_use: Optional[bool] = None


class JoinTokenIssued(SchemaModel):
    """Operator view of a join token the Runtime just issued."""

    token: str = Field(min_length=1)
    expires_at: Timestamp
    single_use: bool
    name: Optional[AgentName] = None
    agent_did: Optional[AgentDid] = None


class RevokeJoinTokenRequest(SchemaModel):
    """Operator input that revokes a join token."""

    token: str = Field(min_length=1)


class RuntimeEvent(SchemaModel):
    """One event pushed on the Session event stream."""

    type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    data: JsonObject


class ToolErrorResult(SchemaModel):
    """Structured MCP tool result when a Runtime operation fails.

    The MCP error flag is set. ``error`` is the unchanged Runtime
    ``ErrorObject``. Readable text is ``code: message``.
    """

    error: ErrorObject


SEND_RESULT_ADAPTER: TypeAdapter[SendResult] = TypeAdapter(SendResult)
REPLY_REQUEST_ADAPTER: TypeAdapter[ReplyRequest] = TypeAdapter(ReplyRequest)


def parse_join_request(data: Any) -> JoinRequest:
    """Parse join input from a mapping. ``spec_version`` is required."""
    return parse_schema(JoinRequest, data)


def parse_join_result(data: Any) -> JoinResult:
    """Parse a JoinResult mapping."""
    if isinstance(data, JoinResult):
        return data
    try:
        return JoinResult.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_send_request(data: Any) -> SendRequest:
    """Parse send input. A request requires ``collect``. ``deadline`` may be omitted."""
    if isinstance(data, (RequestSendRequest, EventSendRequest)):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("send body must be an object")
    kind = data.get("kind")
    try:
        if kind == "event":
            return EventSendRequest.model_validate(data)
        if kind == "request":
            return RequestSendRequest.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc
    raise ValueError("kind must be request or event")


def parse_send_result(data: Any) -> SendResult:
    """Parse a send result, including nested Message and Ticket."""
    if isinstance(data, (AcceptedSendResult, TicketedSendResult)):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("send result must be an object")
    body = dict(data)
    if "message" in body:
        body["message"] = parse_message(body["message"])
    if "ticket" in body:
        body["ticket"] = parse_ticket(body["ticket"])
    try:
        return SEND_RESULT_ADAPTER.validate_python(body)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_reply_request(data: Any) -> ReplyRequest:
    """Parse reply input discriminated on ``outcome``."""
    if isinstance(data, (ReplySuccessRequest, ReplyFailureRequest)):
        return data
    try:
        return REPLY_REQUEST_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_lease_result(data: Any) -> LeaseResult:
    """Parse a lease result, including nested Deliveries."""
    if isinstance(data, LeaseResult):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("lease result must be an object")
    deliveries = data.get("deliveries") or []
    if not isinstance(deliveries, list):
        raise ValueError("deliveries must be an array")
    parsed = [parse_delivery(item) for item in deliveries]
    try:
        return LeaseResult.model_validate({"deliveries": parsed})
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_lease_request(data: Any) -> LeaseRequest:
    """Parse lease input. An empty object is valid."""
    if data is None:
        data = {}
    return parse_schema(LeaseRequest, data)


def parse_complete_request(data: Any) -> CompleteRequest:
    """Parse complete input."""
    return parse_schema(CompleteRequest, data)


def parse_renew_request(data: Any) -> RenewRequest:
    """Parse renew input."""
    return parse_schema(RenewRequest, data)


def parse_find_request(data: Any) -> FindRequest:
    """Parse Directory find input."""
    return parse_schema(FindRequest, data)


def parse_issue_join_token_request(data: Any) -> IssueJoinTokenRequest:
    """Parse operator token issuance input."""
    if data is None:
        data = {}
    return parse_schema(IssueJoinTokenRequest, data)


def parse_revoke_join_token_request(data: Any) -> RevokeJoinTokenRequest:
    """Parse operator token revoke input."""
    return parse_schema(RevokeJoinTokenRequest, data)


def parse_history_result(data: Any) -> HistoryResult:
    """Parse a history page, including nested Messages."""
    if isinstance(data, HistoryResult):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("history result must be an object")
    messages = data.get("messages") or []
    if not isinstance(messages, list):
        raise ValueError("messages must be an array")
    body: dict[str, Any] = {
        "messages": [parse_message(item) for item in messages],
        "has_more": data.get("has_more"),
    }
    next_before = data.get("next_before")
    if next_before is not None:
        body["next_before"] = next_before
    try:
        return HistoryResult.model_validate(body)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def tell_view(result: AcceptedSendResult) -> TellView:
    """Project an accepted event send into the model-facing TellView."""
    if result.message.thread_id is None:
        return TellView(status="accepted")
    return TellView(status="accepted", thread_id=result.message.thread_id)


def history_view(result: HistoryResult) -> HistoryView:
    """Project wire history Messages into the model-facing HistoryView."""
    body: dict[str, Any] = {
        "messages": [_history_turn(message) for message in result.messages],
        "has_more": result.has_more,
    }
    if result.next_before is not None:
        body["next_before"] = result.next_before
    return HistoryView.model_validate(body)


def _history_turn(message: Message) -> HistoryTurn:
    if message.seq is None:
        raise ValueError("history turns require seq")
    base: dict[str, Any] = {
        "id": message.id,
        "seq": message.seq,
        "sender": message.sender,
        "created_at": message.created_at,
    }
    if isinstance(message, ErrorMessage):
        return HistoryErrorTurn.model_validate(
            {
                **base,
                "kind": "error",
                "parent_id": message.parent_id,
                "error": {
                    "code": message.error.code,
                    "message": message.error.message,
                },
            }
        )
    if isinstance(message, ResponseMessage):
        return HistoryResponseTurn.model_validate(
            {
                **base,
                "kind": "response",
                "parent_id": message.parent_id,
                "content": message.content,
            }
        )
    return _HISTORY_CONTENT[message.kind].model_validate(
        {**base, "kind": message.kind, "content": message.content}
    )


_HISTORY_CONTENT = {
    "request": HistoryRequestTurn,
    "event": HistoryEventTurn,
}
