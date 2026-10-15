"""Request and result bodies for advanced Runtime clients.

`BaseAgent` builds these requests for ordinary agent code. Transport authors
use the wire bodies for admission, delivery and collection. Model-facing
views keep the same outcomes with less data; use their own parsers.
"""

from __future__ import annotations

from typing import Annotated, Literal, Mapping, Optional, Union

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
    """Short-lived challenge used to prove Agent DID control.

    A DID is the Agent's `did:key` identity. The Client signs this
    challenge with `issue_identity_proof` and sends the JWT as
    `identity_proof` on join.

    Attributes:
        nonce: At least 128 bits of random data in base64url form.
        audience: Exact JWT audience required by the Runtime.
        expires_at: Time after which this challenge cannot authenticate a join.
    """

    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{22,64}$")
    audience: str = Field(
        pattern=r"^agentconnect:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
    )
    expires_at: Timestamp


class JoinRequest(SchemaModel):
    """Create or reconnect a Membership and open a Session for one running Instance.

    `spec_version` is required on the wire. `Team.join` supplies it for keyword
    calls. Reconnection needs the retained Agent DID and, on authenticated joins,
    valid admission credentials and a fresh identity proof.

    Attributes:
        name: Requested name, canonicalized by the Runtime.
        agent_did: Identity bound to the Membership; a new key cannot reclaim it.
        profile: Replaces the Membership's discovery information.
        instance_id: Omit to allocate an Instance. Reusing it replaces that
            Instance's Session, invalidating its old token.
        max_in_flight: Caps active Delivery leases, including deferred replies;
            omission lets the Runtime use one.
        join_token: Team invitation required for authenticated admission.
        identity_proof: Fresh proof of Agent key control for authenticated admission.
        delivery_history: Omit for Message bodies; ids mode leaves Delivery history
            bodies empty and supplies earlier Message ids.
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

    Attributes:
        max_message_bytes: Maximum UTF-8 JSON bytes of a `send` or `reply`
            body. HTTP applies the same budget to every JSON request body.
        max_mailbox_depth: Maximum queued plus leased Mailbox items before
            `send` returns `busy`.
        delivery_history_limit: Maximum earlier Thread Messages included
            in a Delivery `history` window.
        wait_hold_seconds: Seconds a `collect="wait"` send may stay open.
        max_held_waits: Maximum concurrent `collect="wait"` sends one
            Membership may hold. Further waits fail with `wait_limit`.
        work_lifetime_seconds: Cutoff stamped on a new request whose send
            omitted `deadline` and that has no request parent to inherit from.
        max_deadline_seconds: Farthest a new request deadline may be from
            acceptance.
        max_open_tickets: Maximum open Tickets one Membership may hold as
            requester. A Ticket is the durable record for one request.
        replay_horizon_seconds: Seconds after an obligation ends during
            which an identical retry returns the original result.
        max_retained_bytes: Maximum UTF-8 JSON bytes of retained Message
            bodies this Runtime keeps.
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
    """Result of a successful join.

    Attributes:
        session_token: Bearer credential for the new Session.
        session_expires_at: Current Session expiry.
        address: Canonical qualified Address assigned to the Membership.
        team_name: Canonical name of the Team served by this Runtime.
        agent_did: Verified `did:key` bound to the Membership.
        instance_id: Instance id for this Session, assigned when omitted.
        persistence: Runtime restart guarantee, `volatile` or `durable`.
        limits: Operational limits this Runtime enforces.
        spec_version: Exact public contract version implemented by the Runtime.
    """

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
    """Current Session expiry after renewal; Delivery leases are renewed separately."""

    session_expires_at: Timestamp


class SendBase(SchemaModel):
    """Work or information addressed to one teammate.

    Attributes:
        id: Proposed Message id and replay key. Retry the same body under the
            same id; changing accepted data fails with `id_conflict`.
        recipient: Local name or qualified Address within this Team.
        content: Application data, including JSON null.
        thread_id: Groups conversation history for its fixed participants.
        parent_id: Authorized Message causing or continued by this send; carries
            its trace into this work, even across Threads.
        metadata: Application data that does not control Runtime decisions.
    """

    id: Uuid
    recipient: Address
    content: JsonValue
    thread_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None
    metadata: Optional[JsonObject] = None


class RequestSendRequest(SendBase):
    """Send work that expects a reply and opens a Ticket.

    Attributes:
        collect: `ticket` returns immediately; `wait` holds until a terminal
            result or the Runtime wait bound. Either can return an open Ticket.
        deadline: Future absolute work cutoff. Omit to inherit a request parent's
            deadline, or receive the Runtime work lifetime when there is no request
            parent. Ending collection does not cancel accepted work.
    """

    kind: Literal["request"]
    collect: CollectMode
    deadline: Optional[Timestamp] = None


class EventSendRequest(SendBase):
    """Send information without creating a Ticket or expecting a reply."""

    kind: Literal["event"]


SendRequest = Union[RequestSendRequest, EventSendRequest]
"""Input to Runtime `send`, discriminated on `kind`."""


class AcceptedSendResult(SchemaModel):
    """Acknowledgement that the event was queued; the recipient may not have handled it yet."""

    status: Literal["accepted"]
    message: EventMessage


class TellView(SchemaModel):
    """Model-facing acknowledgement that an event was queued, with its Thread id when present."""

    status: Literal["accepted"]
    thread_id: Optional[Uuid] = None


class TicketedSendResult(SchemaModel):
    """Accepted request and its current saved result.

    Both collection modes return this wrapper. Branch on `ticket.state` before
    reading its content or error. Save `ticket.id` to collect open work without
    sending another request.
    """

    status: Literal["ticketed"]
    message: RequestMessage
    ticket: Ticket


SendResult = Annotated[
    Union[AcceptedSendResult, TicketedSendResult],
    Field(discriminator="status"),
]
"""Result of Runtime `send`, discriminated on `status`."""


class LeaseRequest(SchemaModel):
    """Pull available work within the Session's in-flight limit.

    Omitting `max_items` requests one attempt. The Runtime may return fewer,
    including none, when no work or capacity is available.
    """

    max_items: Optional[JsonInt] = Field(default=None, ge=1, le=100)


class LeaseResult(SchemaModel):
    """New attempts exclusively leased to this Session; an empty list is a valid result."""

    deliveries: list[Delivery]


class RenewRequest(SchemaModel):
    """Extend a still-active Delivery lease owned by the calling Session."""

    lease_id: Uuid


class RenewResult(SchemaModel):
    """Lease handle and its new expiry; the request work deadline is unchanged."""

    lease_id: Uuid
    lease_expires_at: Timestamp


class CompleteRequest(SchemaModel):
    """Finish a Delivery without replying.

    Completing an event ends its attempt. Completing a request declines it:
    its Ticket becomes terminal with no response or error.
    """

    lease_id: Uuid


class CompleteResult(SchemaModel):
    """Completion acknowledgement; `ticket` is present only for a declined request."""

    ticket: Optional[DeclinedTicket] = None


class ReplyBase(SchemaModel):
    """Reply under an active request lease owned by the Session.

    Attributes:
        id: Proposed reply Message id. Identical retries keep this id and outcome.
        lease_id: Authorizes the current attempt. Replay equality uses the target
            request and reply data, rather than this lease id.
    """

    id: Uuid
    lease_id: Uuid


class ReplySuccessRequest(ReplyBase):
    """Complete a request with successful application content; JSON null is a valid answer."""

    outcome: Literal["completed"]
    content: JsonValue


class ReplyFailureRequest(ReplyBase):
    """Complete a request with failure data safe to reveal to its requester."""

    outcome: Literal["failed"]
    error: ErrorObject


ReplyRequest = Annotated[
    Union[ReplySuccessRequest, ReplyFailureRequest],
    Field(discriminator="outcome"),
]
"""Input to Runtime `reply`, discriminated on `outcome`."""


class ReplyResult(SchemaModel):
    """Terminal Ticket containing the accepted successful or failed reply."""

    ticket: Union[CompletedTicket, FailedTicket]


class GetResultRequest(SchemaModel):
    """Collect the current saved request result.

    Pass `ticket_id` from `ask`, equal to the request Message id. Repeat
    while `state` is `open`. Ending a wait does not cancel work.
    """

    ticket_id: Uuid = Field(
        description=(
            "ticket_id from ask, equal to the request Message id. Repeat "
            "while state is open. Ending a wait does not cancel work."
        )
    )


class GetHistoryRequest(SchemaModel):
    """Thread history lookup.

    Pages are newest-first, but Messages inside a page are oldest to
    newest by `seq`. Pass `next_before` from the previous page as
    `before`. Stop when `has_more` is false.
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

    `messages` are ordered by `seq` ascending. The newest page is
    returned first. When `has_more` is true, pass `next_before` as the
    next `before`.

    Attributes:
        messages: Requested page, oldest to newest by `seq`.
        has_more: True when older retained Messages remain before this page.
        next_before: Pass as the next `before` to load the older page.
    """

    messages: list[Message]
    has_more: bool
    next_before: Optional[Uuid] = None


class HistoryTurnBase(SchemaModel):
    """Fields shared by every model-facing history turn.

    Attributes:
        id: Message id. `HistoryView.next_before` is the paging cursor.
        seq: Thread sequence. History is ordered by `seq` ascending inside a page.
        sender: Address that sent this turn.
        created_at: When the Runtime accepted this Message.
    """

    id: Uuid
    seq: JsonInt = Field(ge=1)
    sender: QualifiedAddress
    created_at: Timestamp


class HistoryRequestTurn(HistoryTurnBase):
    """Work input from a request on a model-facing history page."""

    kind: Literal["request"]
    content: JsonValue


class HistoryEventTurn(HistoryTurnBase):
    """Event content on a model-facing history page."""

    kind: Literal["event"]
    content: JsonValue


class HistoryResponseTurn(HistoryTurnBase):
    """Successful reply content on a model-facing history page.

    `parent_id` identifies the request it answers, equal to that ask's `ticket_id`.
    """

    kind: Literal["response"]
    parent_id: Uuid
    content: JsonValue


class HistoryErrorTurn(HistoryTurnBase):
    """Failed reply on a model-facing history page.

    `parent_id` identifies the request it answers. The error includes only its
    code and message.
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
"""One history turn on a model-facing page, discriminated on `kind`."""


class HistoryView(SchemaModel):
    """Model-facing Thread history page. Same paging as `HistoryResult`.

    MCP `get_history` and Session-bound tools return this projection.
    Runtime and HTTP return `HistoryResult`, as does `BaseAgent.get_history`.

    Attributes:
        messages: Requested page, oldest to newest by `seq`.
        has_more: True when older retained Messages remain before this page.
        next_before: Pass as the next `before` to load the older page.
    """

    messages: list[HistoryTurn]
    has_more: bool
    next_before: Optional[Uuid] = None


class AskToolRequest(SchemaModel):
    """Send work that needs a reply.

    Returns the saved request result as a Ticket view. `collect="wait"`
    (default) may still return `open`; call `get_result` with
    `ticket_id`. A Thread is fixed to its original participants; another
    peer is `forbidden`.
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
    is fixed to its original participants; another peer is `forbidden`.
    Omit `thread_id` for an unthreaded notice; that is the usual path.
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
    """Current agent Directory entries for the MCP roster; principal Memberships are omitted."""

    team_name: TeamName
    members: list[DirectoryEntry]


class TraceEvent(SchemaModel):
    """One recorded step of a causal operation.

    `parent_id` is the parent of `message_id` when that Message has one.
    `get_trace` returns events in recorded order.

    Attributes:
        at: When the Runtime recorded the event.
        type: What happened (`accepted`, `ticket_opened`, `leased`,
            `completed`, `replied`, or `ticket_closed`).
        trace_id: Causal id shared with the Messages in this operation.
        actor: Membership that performed the step, or the requester for
            accept and open.
        message_id: Message this step is about, when there is one.
        parent_id: Parent of `message_id`, copied from that Message.
        ticket_id: Ticket this step is about, when there is one.
        detail: Type-specific fields. Unknown keys are ignored by a Client.
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
    """Result of `get_trace`.

    Attributes:
        trace_id: Requested causal id.
        events: Recorded events, oldest first.
    """

    trace_id: Uuid
    events: list[TraceEvent]


class StatusAgent(SchemaModel):
    """Agent Membership observed by an operator.

    Attributes:
        online: At least one stored Session is unexpired; not proof of handler readiness.
        mailbox_depth: Queued and leased items together.
        open_tickets: Open requests addressed to this Membership.
    """

    kind: Literal["agent"]
    name: AgentName
    address: QualifiedAddress
    online: bool
    mailbox_depth: JsonInt = Field(ge=0)
    open_tickets: JsonInt = Field(ge=0)


class StatusPrincipal(SchemaModel):
    """Principal Membership observed by an operator.

    `online` means at least one stored Session is unexpired. Principals have no
    Mailbox or recipient Ticket counts.
    """

    kind: Literal["principal"]
    name: AgentName
    address: QualifiedAddress
    online: bool


StatusMember = Annotated[
    Union[StatusAgent, StatusPrincipal],
    Field(discriminator="kind"),
]
"""One Membership row in `status`, discriminated on `kind`."""


class StatusResult(SchemaModel):
    """Result of `status`.

    Attributes:
        team_name: Canonical Team name.
        persistence: Runtime restart guarantee.
        origin: HTTP origin when the Runtime is serving, such as
            `http://127.0.0.1:9000`. Omitted when it is not serving.
        open_tickets: Open Tickets in the Team.
        members: Every Membership, including principals such as `operator`.
    """

    team_name: TeamName
    persistence: PersistenceMode
    origin: Optional[str] = None
    open_tickets: JsonInt = Field(ge=0)
    members: list[StatusMember]


class IssueJoinTokenRequest(SchemaModel):
    """Operator input that creates a join token.

    Attributes:
        name: Bind the token to this Agent name.
        agent_did: Bind the token to this Agent DID (`did:key`).
        ttl_seconds: Lifetime in seconds. Omit to use the Runtime default.
        single_use: First admission consumes the token. It can then reconnect
            only the Membership it admitted, while valid and unrevoked.
    """

    name: Optional[AgentName] = None
    agent_did: Optional[AgentDid] = None
    ttl_seconds: Optional[JsonFloat] = Field(default=None, ge=1)
    single_use: Optional[bool] = None


class JoinTokenIssued(SchemaModel):
    """Operator view of a join token the Runtime just issued.

    Attributes:
        token: Secret the Agent sends as `join_token`. Keep it out of
            logs and Messages.
        expires_at: Time after which this token cannot authenticate a join.
        single_use: Whether first admission consumes the token; subsequent use
            can reconnect only the admitted Membership.
        name: Bound Agent name, when the operator set one.
        agent_did: Bound Agent DID, when the operator set one.
    """

    token: str = Field(min_length=1)
    expires_at: Timestamp
    single_use: bool
    name: Optional[AgentName] = None
    agent_did: Optional[AgentDid] = None


class RevokeJoinTokenRequest(SchemaModel):
    """Revoke admission and invalidate Sessions created from this token at their next auth check."""

    token: str = Field(min_length=1)


class RuntimeEvent(SchemaModel):
    """Session event whose `type` selects its data shape.

    Ignore unknown types. `work_available` has empty data and is a hint to lease;
    `trace` carries a TraceEvent. Receiving a hint is not required for delivery.
    """

    type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    data: JsonObject


class ToolErrorResult(SchemaModel):
    """Structured MCP tool result when a Runtime operation fails.

    The MCP error flag is set. `error` is the unchanged Runtime
    `ErrorObject`. Readable text is `code: message`. Malformed arguments
    and authentication failures stay MCP-level errors, not this object.

    Attributes:
        error: Runtime failure preserved without reinterpretation.
    """

    error: ErrorObject


SEND_RESULT_ADAPTER: TypeAdapter[SendResult] = TypeAdapter(SendResult)
REPLY_REQUEST_ADAPTER: TypeAdapter[ReplyRequest] = TypeAdapter(ReplyRequest)


def parse_join_request(data: object) -> JoinRequest:
    """Parse join input from a mapping. `spec_version` is required.

    Args:
        data: JSON object, or an already parsed `JoinRequest`.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    return parse_schema(JoinRequest, data)


def parse_join_result(data: object) -> JoinResult:
    """Parse a `JoinResult` mapping.

    Args:
        data: JSON object, or an already parsed `JoinResult`.

    Raises:
        ValueError: Validation fails.
    """
    if isinstance(data, JoinResult):
        return data
    try:
        return JoinResult.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_send_request(data: object) -> SendRequest:
    """Parse send input. A request requires `collect`. `deadline` may be omitted.

    Args:
        data: JSON object, or an already parsed send request.

    Raises:
        ValueError: `data` is not an object, `kind` is unknown, or
            validation fails.
    """
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


def parse_send_result(data: object) -> SendResult:
    """Parse a send result, including nested Message and Ticket.

    Args:
        data: JSON object, or an already parsed send result.

    Raises:
        ValueError: `data` is not an object, or nested validation fails.
    """
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


def parse_reply_request(data: object) -> ReplyRequest:
    """Parse reply input discriminated on `outcome`.

    Args:
        data: JSON object, or an already parsed reply request.

    Raises:
        ValueError: Validation fails.
    """
    if isinstance(data, (ReplySuccessRequest, ReplyFailureRequest)):
        return data
    try:
        return REPLY_REQUEST_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_lease_result(data: object) -> LeaseResult:
    """Parse a lease result, including nested Deliveries.

    Args:
        data: JSON object, or an already parsed `LeaseResult`.

    Raises:
        ValueError: `data` is not an object, `deliveries` is not an array,
            or nested validation fails.
    """
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


def parse_lease_request(data: object) -> LeaseRequest:
    """Parse lease input. An empty object is valid.

    Args:
        data: JSON object, `None` (treated as empty), or a `LeaseRequest`.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    if data is None:
        data = {}
    return parse_schema(LeaseRequest, data)


def parse_complete_request(data: object) -> CompleteRequest:
    """Parse complete input.

    Args:
        data: JSON object, or an already parsed `CompleteRequest`.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    return parse_schema(CompleteRequest, data)


def parse_renew_request(data: object) -> RenewRequest:
    """Parse renew input.

    Args:
        data: JSON object, or an already parsed `RenewRequest`.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    return parse_schema(RenewRequest, data)


def parse_find_request(data: object) -> FindRequest:
    """Parse Directory find input.

    Args:
        data: JSON object, or an already parsed `FindRequest`.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    return parse_schema(FindRequest, data)


def parse_issue_join_token_request(data: object) -> IssueJoinTokenRequest:
    """Parse operator token issuance input.

    Args:
        data: JSON object, `None` (treated as empty), or a parsed request.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    if data is None:
        data = {}
    return parse_schema(IssueJoinTokenRequest, data)


def parse_revoke_join_token_request(data: object) -> RevokeJoinTokenRequest:
    """Parse operator token revoke input.

    Args:
        data: JSON object, or an already parsed `RevokeJoinTokenRequest`.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    return parse_schema(RevokeJoinTokenRequest, data)


def parse_history_result(data: object) -> HistoryResult:
    """Parse a history page, including nested Messages.

    Args:
        data: JSON object, or an already parsed `HistoryResult`.

    Raises:
        ValueError: `data` is not an object, `messages` is not an array,
            or nested validation fails.
    """
    if isinstance(data, HistoryResult):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("history result must be an object")
    messages = data.get("messages") or []
    if not isinstance(messages, list):
        raise ValueError("messages must be an array")
    body: dict[str, object] = {
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
    """Return event acceptance and its Thread id, leaving out the Message envelope."""
    if result.message.thread_id is None:
        return TellView(status="accepted")
    return TellView(status="accepted", thread_id=result.message.thread_id)


def history_view(result: HistoryResult) -> HistoryView:
    """Return compact history turns with unchanged ordering and paging cursors.

    Keeps reply correlation through `parent_id`; omits wire identity, recipient,
    metadata and trace fields. Failures retain only code and message.
    """
    body: dict[str, object] = {
        "messages": [_history_turn(message) for message in result.messages],
        "has_more": result.has_more,
    }
    if result.next_before is not None:
        body["next_before"] = result.next_before
    return HistoryView.model_validate(body)


def _history_turn(message: Message) -> HistoryTurn:
    if message.seq is None:
        raise ValueError("history turns require seq")
    base: JsonObject = {
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


_HISTORY_CONTENT: dict[str, type[HistoryRequestTurn] | type[HistoryEventTurn]] = {
    "request": HistoryRequestTurn,
    "event": HistoryEventTurn,
}
