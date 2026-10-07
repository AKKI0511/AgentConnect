"""Ticket union discriminated on ``state``, plus model-facing TicketView."""

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

    Read completion from ``state``. A completed Ticket carries
    ``response``; a failed or expired Ticket carries ``error``. Do not
    treat missing content as pending, declined, and failed at once.

    ``trace_id`` is the request Message's causal id, retained so
    ``get_result`` can feed ``get_trace`` after Session replacement.
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
    """Ticket completed by one successful response."""

    state: Literal["completed"]
    response: ResponseMessage

    @property
    def content(self) -> JsonValue:
        """The response body. Present only on a completed Ticket."""
        return self.response.content


class FailedTicket(TicketBase):
    """Ticket completed by an Agent or Runtime failure."""

    state: Literal["failed"]
    error: ErrorObject


class ExpiredTicket(TicketBase):
    """Ticket whose deadline passed before an accepted reply."""

    state: Literal["expired"]
    error: DeadlineExceededError


class DeclinedTicket(TicketBase):
    """Ticket the recipient deliberately declined."""

    state: Literal["declined"]


Ticket = Annotated[
    Union[OpenTicket, CompletedTicket, FailedTicket, ExpiredTicket, DeclinedTicket],
    Field(discriminator="state"),
]

TICKET_ADAPTER: TypeAdapter[Ticket] = TypeAdapter(Ticket)


def parse_ticket(data: Any) -> Ticket:
    """Parse a Ticket mapping discriminated on ``state``."""
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
    """Lean failure on a model-facing Ticket view."""

    code: ErrorCode
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class TicketViewBase(SchemaModel):
    """Fields shared by every model-facing Ticket view.

    Branch on ``state``. Timing is not proof of state. A completed
    Ticket stays completed after its original deadline while retained.
    """

    ticket_id: Uuid
    thread_id: Optional[Uuid] = None


class OpenTicketView(TicketViewBase):
    """Open Ticket. Keep ``ticket_id`` and call ``get_result``."""

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
    """Model-facing view of a completed Ticket."""

    state: Literal["completed"]
    content: JsonValue


class FailedTicketView(TicketViewBase):
    """Model-facing view of a failed Ticket."""

    state: Literal["failed"]
    error: TicketViewError


class ExpiredTicketView(TicketViewBase):
    """Model-facing view of an expired Ticket."""

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

TICKET_VIEW_ADAPTER: TypeAdapter[TicketView] = TypeAdapter(TicketView)


def parse_ticket_view(data: Any) -> TicketView:
    """Parse a TicketView mapping discriminated on ``state``."""
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
    """Project a wire Ticket into the model-facing TicketView."""
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
