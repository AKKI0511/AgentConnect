"""Ticket union discriminated on ``state``."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError

from agentconnect.core.base import JsonInt, JsonValue, SchemaModel, validation_message
from agentconnect.core.error import DeadlineExceededError, ErrorObject
from agentconnect.core.message import ResponseMessage
from agentconnect.core.primitives import QualifiedAddress, Timestamp, Uuid

__all__ = [
    "TicketBase",
    "OpenTicket",
    "CompletedTicket",
    "FailedTicket",
    "ExpiredTicket",
    "DeclinedTicket",
    "Ticket",
    "parse_ticket",
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
