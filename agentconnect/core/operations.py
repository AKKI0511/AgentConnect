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
    EventMessage,
    Message,
    RequestMessage,
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
    parse_ticket,
)

__all__ = [
    "JoinChallenge",
    "JoinRequest",
    "RuntimeLimits",
    "JoinResult",
    "HeartbeatResult",
    "SendBase",
    "AddressCallbackTarget",
    "UrlCallbackTarget",
    "CallbackTarget",
    "RequestSendRequest",
    "EventSendRequest",
    "SendRequest",
    "AcceptedSendResult",
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
    """Fields shared by request and event sends."""

    id: Uuid
    recipient: Address
    content: JsonValue
    thread_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None
    metadata: Optional[JsonObject] = None


class AddressCallbackTarget(SchemaModel):
    """Callback target that delivers the result as a Message."""

    address: Address


class UrlCallbackTarget(SchemaModel):
    """Callback target that POSTs the result to an HTTPS URL."""

    url: str = Field(min_length=1)


CallbackTarget = Union[AddressCallbackTarget, UrlCallbackTarget]


class RequestSendRequest(SendBase):
    """Send a request. Always opens a Ticket.

    ``collect`` is required. ``deadline`` may be omitted; the Runtime
    stamps the effective cutoff on the accepted Message. Fire-and-forget
    work is :class:`EventSendRequest`.

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
    callback: Optional[CallbackTarget] = None


class EventSendRequest(SendBase):
    """Send information without a reply."""

    kind: Literal["event"]


SendRequest = Union[RequestSendRequest, EventSendRequest]


class AcceptedSendResult(SchemaModel):
    """Result for an event."""

    status: Literal["accepted"]
    message: EventMessage


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
    """Ticket lookup used by non-HTTP bindings."""

    ticket_id: Uuid


class GetHistoryRequest(SchemaModel):
    """Thread history lookup."""

    thread_id: Uuid
    before: Optional[Uuid] = None
    limit: Optional[JsonInt] = Field(default=None, ge=1, le=200)


class HistoryResult(SchemaModel):
    """One page of retained Thread history, ordered by ``seq`` ascending."""

    messages: list[Message]
    has_more: bool


class AskToolRequest(SchemaModel):
    """MCP ``ask`` arguments.

    Omit ``idempotency_key`` to mint a fresh Message id. Pass a key only
    when a retry must collapse onto the same Ticket. ``collect="wait"``
    returns the current Ticket after the Runtime hold, which may still
    be ``open``.
    """

    recipient: Address
    content: JsonValue
    deadline_seconds: Optional[JsonInt] = Field(default=None, ge=1, le=86400)
    collect: CollectMode = "wait"
    thread_id: Optional[Uuid] = None
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=200)


class TellToolRequest(SchemaModel):
    """MCP ``tell`` arguments.

    Omit ``idempotency_key`` to mint a fresh Message id. Pass a key only
    when a retry must collapse onto the same event.
    """

    recipient: Address
    content: JsonValue
    thread_id: Optional[Uuid] = None
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=200)


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
    """Structured result used when an MCP tool reaches a Runtime failure."""

    error: ErrorObject


SEND_RESULT_ADAPTER = TypeAdapter(SendResult)
REPLY_REQUEST_ADAPTER = TypeAdapter(ReplyRequest)
CALLBACK_TARGET_ADAPTER = TypeAdapter(CallbackTarget)


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
    if kind == "event":
        cls: type[SchemaModel] = EventSendRequest
    elif kind == "request":
        cls = RequestSendRequest
    else:
        raise ValueError("kind must be request or event")
    try:
        return cls.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


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
    try:
        return HistoryResult.model_validate(
            {
                "messages": [parse_message(item) for item in messages],
                "has_more": data.get("has_more"),
            }
        )
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc
