"""Ticket union discriminated on `state`, plus model-facing TicketView.

A Ticket is the requester's durable record for one request Message. Its
id equals that request id. Read completion from `state`: `open`,
`completed`, `failed`, `expired`, or `declined`. MCP `ask` / `get_result`
return `TicketView`; Runtime, HTTP, and Client `ask` return the wire Ticket.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError

from agentconnect.core.base import JsonInt, JsonValue, SchemaModel, validation_message
from agentconnect.core.error import DeadlineExceededError, ErrorObject
from agentconnect.core.message import ResponseMessage
from agentconnect.core.primitives import ErrorCode, QualifiedAddress, Timestamp, Uuid

__all__ = [
    "TicketBase",
    "OpenTicket",
    "CompletedTicket",
    "FailedTicket",
    "ExpiredTicket",
    "DeclinedTicket",
    "Ticket",
    "parse_ticket",
    "TicketViewError",
    "TicketViewBase",
    "OpenTicketView",
    "CompletedTicketView",
    "FailedTicketView",
    "ExpiredTicketView",
    "DeclinedTicketView",
    "TicketView",
    "ticket_view",
    "parse_ticket_view",
]


class TicketBase(SchemaModel):
    """Fields shared by every Ticket state.

    Read completion from `state`. A completed Ticket carries `response`;
    a failed or expired Ticket carries `error`. Do not treat missing
    content as pending, declined, and failed at once.

    `trace_id` is the request Message's causal id, retained so
    `get_result` can feed `get_trace` after Session replacement.

    Attributes:
        id: Request Message id.
        requester: Membership that sent the request and owns this Ticket.
        recipient: Membership asked to handle the request.
        thread_id: Conversation the request belongs to, when it has one.
        trace_id: Causal id of the request this Ticket records.
        created_at: Request acceptance time.
        updated_at: Time of the last state transition or late-reply observation.
        deadline: Absolute time after which an open Ticket expires.
        late_reply_count: Distinct replies observed after this Ticket
            became terminal.
    """

    id: Uuid
    requester: QualifiedAddress
    recipient: QualifiedAddress
    thread_id: Optional[Uuid] = None
    trace_id: Uuid
    created_at: Timestamp
    updated_at: Timestamp
    deadline: Timestamp
    late_reply_count: JsonInt = Field(ge=0)


class OpenTicket(TicketBase):
    """Ticket waiting for its first accepted reply."""

    state: Literal["open"]


class CompletedTicket(TicketBase):
    """Ticket completed by one successful response.

    Attributes:
        state: Always `completed`.
        response: Immutable winning response Message.
    """

    state: Literal["completed"]
    response: ResponseMessage

    @property
    def content(self) -> JsonValue:
        """The response body. Present only on a completed Ticket."""
        return self.response.content


class FailedTicket(TicketBase):
    """Ticket completed by an Agent or Runtime failure.

    Attributes:
        state: Always `failed`.
        error: Immutable winning failure.
    """

    state: Literal["failed"]
    error: ErrorObject


class ExpiredTicket(TicketBase):
    """Ticket whose deadline passed before an accepted reply.

    Attributes:
        state: Always `expired`.
        error: Fixed `deadline_exceeded` failure.
    """

    state: Literal["expired"]
    error: DeadlineExceededError


class DeclinedTicket(TicketBase):
    """Ticket the recipient deliberately declined.

    The recipient handled the request and chose not to answer. This is a
    terminal, non-failure outcome, distinct from a handler failure and
    from a deadline that expired with no handling.
    """

    state: Literal["declined"]


Ticket = Annotated[
    Union[OpenTicket, CompletedTicket, FailedTicket, ExpiredTicket, DeclinedTicket],
    Field(discriminator="state"),
]
"""Requester-owned durable result record, discriminated on `state`."""

TICKET_ADAPTER: TypeAdapter[Ticket] = TypeAdapter(Ticket)


def parse_ticket(data: Any) -> Ticket:
    """Parse a Ticket mapping discriminated on `state`.

    Args:
        data: JSON object, or an already parsed Ticket instance.

    Returns:
        A frozen Ticket of the matching state.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    if isinstance(
        data,
        (OpenTicket, CompletedTicket, FailedTicket, ExpiredTicket, DeclinedTicket),
    ):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("ticket must be an object")
    try:
        return TICKET_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


OPEN_STATUS_MESSAGE = (
    "Waiting for a reply. Keep ticket_id and call get_result; do not send a new ask."
)
DECLINED_STATUS_MESSAGE = (
    "The recipient declined. This is not a failure. Try another "
    "specialist or add context."
)


class TicketViewError(SchemaModel):
    """Lean failure on a model-facing Ticket view.

    Code and message only. No details, retryable flag, or Message envelope.

    Attributes:
        code: Well-known failure code.
        message: Requester-visible explanation.
    """

    code: ErrorCode
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class TicketViewBase(SchemaModel):
    """Fields shared by every model-facing Ticket view.

    Branch on `state`. Timing is not proof of state. A completed Ticket
    stays completed after its original deadline while retained.

    Attributes:
        ticket_id: Request Message id. The only id on this view.
        thread_id: Conversation the request belongs to, when it has one.
    """

    ticket_id: Uuid
    thread_id: Optional[Uuid] = None


class OpenTicketView(TicketViewBase):
    """Open Ticket. Keep `ticket_id` and call `get_result`."""

    state: Literal["open"]
    deadline: Timestamp = Field(
        description=(
            "Absolute work cutoff stamped at acceptance. Not an ETA, "
            "not a wait bound, and not proof of state."
        )
    )
    poll_interval_ms: Literal[1000] = Field(
        description=(
            "Hint for how often to call get_result while open. Not a wait "
            "bound, work duration, or lease change. Do not send a new ask."
        )
    )
    status_message: str = Field(
        description=(
            "Next action while open: keep ticket_id and call get_result; "
            "do not send a new ask."
        )
    )


class CompletedTicketView(TicketViewBase):
    """Model-facing view of a completed Ticket.

    Attributes:
        state: Always `completed`.
        content: Reply content alone.
    """

    state: Literal["completed"]
    content: JsonValue


class FailedTicketView(TicketViewBase):
    """Model-facing view of a failed Ticket.

    Attributes:
        state: Always `failed`.
        error: Failure code and message only.
    """

    state: Literal["failed"]
    error: TicketViewError


class ExpiredTicketView(TicketViewBase):
    """Model-facing view of an expired Ticket.

    Attributes:
        state: Always `expired`.
        error: Deadline failure code and message only.
    """

    state: Literal["expired"]
    error: TicketViewError


class DeclinedTicketView(TicketViewBase):
    """Model-facing view of a declined Ticket."""

    state: Literal["declined"]
    status_message: str = Field(
        description=(
            "Next action: this is not a failure. Try another specialist or add context."
        )
    )


TicketView = Annotated[
    Union[
        OpenTicketView,
        CompletedTicketView,
        FailedTicketView,
        ExpiredTicketView,
        DeclinedTicketView,
    ],
    Field(discriminator="state"),
]
"""Model-facing Ticket projection, discriminated on `state` with the same states as the wire union."""

TICKET_VIEW_ADAPTER: TypeAdapter[TicketView] = TypeAdapter(TicketView)


def parse_ticket_view(data: Any) -> TicketView:
    """Parse a TicketView mapping discriminated on `state`.

    Args:
        data: JSON object, or an already parsed TicketView instance.

    Returns:
        A frozen TicketView of the matching state.

    Raises:
        ValueError: `data` is not an object, or validation fails.
    """
    if isinstance(
        data,
        (
            OpenTicketView,
            CompletedTicketView,
            FailedTicketView,
            ExpiredTicketView,
            DeclinedTicketView,
        ),
    ):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("ticket view must be an object")
    try:
        return TICKET_VIEW_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def ticket_view(ticket: Ticket) -> TicketView:
    """Project a wire Ticket into the model-facing TicketView.

    Args:
        ticket: Wire Ticket returned by Runtime, HTTP, or Client `ask`.

    Returns:
        The lean view MCP `ask` / `get_result` and Session-bound tools return.

    Examples:
        Branch on `state` after a model-facing collect:

        ```python
        from agentconnect.core.ticket import ticket_view

        view = ticket_view(ticket)
        if view.state == "completed":
            view.content
        ```
    """
    base: dict[str, Any] = {"ticket_id": ticket.id}
    if ticket.thread_id is not None:
        base["thread_id"] = ticket.thread_id
    if ticket.state == "open":
        return OpenTicketView.model_validate(
            {
                **base,
                "state": "open",
                "deadline": ticket.deadline,
                "poll_interval_ms": 1000,
                "status_message": OPEN_STATUS_MESSAGE,
            }
        )
    if ticket.state == "completed":
        return CompletedTicketView.model_validate(
            {**base, "state": "completed", "content": ticket.response.content}
        )
    if ticket.state == "failed":
        return FailedTicketView.model_validate(
            {
                **base,
                "state": "failed",
                "error": {"code": ticket.error.code, "message": ticket.error.message},
            }
        )
    if ticket.state == "expired":
        return ExpiredTicketView.model_validate(
            {
                **base,
                "state": "expired",
                "error": {"code": ticket.error.code, "message": ticket.error.message},
            }
        )
    return DeclinedTicketView.model_validate(
        {
            **base,
            "state": "declined",
            "status_message": DECLINED_STATUS_MESSAGE,
        }
    )
