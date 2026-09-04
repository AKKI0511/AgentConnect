"""Runtime operation requests and results from the public schema."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError

from agentconnect.core.base import (
    JsonObject,
    JsonValue,
    SchemaModel,
    validation_message,
)
from agentconnect.core.directory import DirectoryEntry
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
from agentconnect.core.spec import SPEC_VERSION
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
    "parse_lease_result",
    "parse_history_result",
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

    ``delivery_history="ids"`` puts earlier Message ids on each Delivery
    instead of Message bodies. Omit it to receive bodies.
    """

    spec_version: SpecVersion = SPEC_VERSION
    name: AgentName
    agent_did: AgentDid
    profile: AgentProfile
    instance_id: Optional[Uuid] = None
    max_in_flight: Optional[int] = Field(default=None, ge=1, le=100)
    join_token: Optional[str] = Field(default=None, min_length=1)
    identity_proof: Optional[str] = Field(default=None, min_length=1)
    delivery_history: Optional[DeliveryHistoryForm] = None


class RuntimeLimits(SchemaModel):
    """Fixed operational limits a Runtime reports at join.

    ``max_held_waits`` caps concurrent ``collect=wait`` sends per
    Membership. ``max_mailbox_depth`` caps queued plus leased Mailbox
    items. Both are exact counts this Runtime enforces.
    """

    max_message_bytes: int = Field(ge=1)
    max_mailbox_depth: int = Field(ge=1)
    delivery_history_limit: int = Field(ge=0)
    wait_hold_seconds: float = Field(ge=0)
    max_held_waits: int = Field(ge=0)


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

    ``collect`` and ``deadline`` are required. Fire-and-forget work is
    :class:`EventSendRequest`.

        RequestSendRequest(
            id=message_id,
            recipient="writer",
            content={"task": "draft this"},
            collect="ticket",
            deadline="2026-08-18T15:10:00Z",
        )
    """

    kind: Literal["request"] = "request"
    collect: CollectMode
    deadline: Timestamp
    callback: Optional[CallbackTarget] = None


class EventSendRequest(SendBase):
    """Send information without a reply."""

    kind: Literal["event"] = "event"


SendRequest = Union[RequestSendRequest, EventSendRequest]


class AcceptedSendResult(SchemaModel):
    """Result for an event."""

    status: Literal["accepted"] = "accepted"
    message: EventMessage


class TicketedSendResult(SchemaModel):
    """Result for a request."""

    status: Literal["ticketed"] = "ticketed"
    message: RequestMessage
    ticket: Ticket


SendResult = Annotated[
    Union[AcceptedSendResult, TicketedSendResult],
    Field(discriminator="status"),
]


class LeaseRequest(SchemaModel):
    """Input to pull available work."""

    max_items: Optional[int] = Field(default=None, ge=1, le=100)


class LeaseResult(SchemaModel):
    """Deliveries currently leased to the Session."""

    deliveries: list[Delivery]


class CompleteRequest(SchemaModel):
    """Finish one Delivery without a response.

    An event just ends. A request is declined.
    """

    lease_id: Uuid


class CompleteResult(SchemaModel):
    """Result of ``complete``."""

    ticket: Optional[DeclinedTicket] = None


class ReplyBase(SchemaModel):
    """Fields shared by successful and failed replies."""

    id: Uuid
    lease_id: Uuid


class ReplySuccessRequest(ReplyBase):
    """Complete a Delivery with successful content."""

    outcome: Literal["completed"] = "completed"
    content: JsonValue


class ReplyFailureRequest(ReplyBase):
    """Complete a Delivery with a safe error."""

    outcome: Literal["failed"] = "failed"
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
    limit: Optional[int] = Field(default=None, ge=1, le=200)


class HistoryResult(SchemaModel):
    """One page of retained Thread history, ordered by ``seq`` ascending."""

    messages: list[Message]
    has_more: bool


class AskToolRequest(SchemaModel):
    """MCP ``ask`` arguments.

    Omit ``idempotency_key`` to mint a fresh Message id. Pass a key only
    when a retry must collapse onto the same Ticket.
    """

    recipient: Address
    content: JsonValue
    deadline_seconds: int = Field(ge=1, le=86400)
    wait_seconds: Optional[float] = Field(default=None, ge=0, le=30)
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


class StatusMember(SchemaModel):
    """One Membership row in ``status``."""

    name: AgentName
    address: QualifiedAddress
    online: bool
    mailbox_depth: int = Field(ge=0)
    open_tickets: int = Field(ge=0)


class StatusResult(SchemaModel):
    """Result of ``status``."""

    team_name: TeamName
    persistence: PersistenceMode
    origin: Optional[str] = None
    open_tickets: int = Field(ge=0)
    members: list[StatusMember]


class IssueJoinTokenRequest(SchemaModel):
    """Operator input that creates a join token."""

    name: Optional[AgentName] = None
    agent_did: Optional[AgentDid] = None
    ttl_seconds: Optional[float] = Field(default=None, ge=1)
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
    """Parse join input from kwargs or a mapping."""
    if isinstance(data, JoinRequest):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("join body must be an object")
    try:
        return JoinRequest.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_join_result(data: Any) -> JoinResult:
    """Parse a JoinResult mapping."""
    if isinstance(data, JoinResult):
        return data
    try:
        return JoinResult.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_send_request(data: Any) -> SendRequest:
    """Parse send input. A request requires ``collect`` and ``deadline``."""
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
