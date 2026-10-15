"""Saved request results and their model-facing views.

`BaseAgent.ask` and `get_result` return a wire Ticket: its `id` is the
request Message id. MCP and Session-bound tools return a `TicketView`,
whose handle is `ticket_id`. Both use the same `state` values; their
fields are not interchangeable.

Examples:
    For a joined `agent` in an async context, with `ticket_id` saved from
    an earlier ask, collect the existing request:

    ```python
    ticket = await agent.get_result(ticket_id)
    if ticket.state == "completed":
        print(ticket.content)
    elif ticket.state in {"failed", "expired"}:
        print(ticket.error.message)
    elif ticket.state == "open":
        print("Still pending; keep", ticket.id)
    else:
        print("The recipient declined; there is no reply.")
    ```
"""

from __future__ import annotations

from typing import Annotated, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError

from agentconnect.core.base import (
    JsonObject,
    JsonInt,
    JsonValue,
    SchemaModel,
    validation_message,
)
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
    """The requester's saved result for one request.

    Branch on `state`: completed work has a response, failed or expired work
    has an error, and declined work has neither. An open Ticket can be collected
    again by its existing `id`; another ask submits new work.

    Attributes:
        id: Also the request Message id.
        requester: Membership that owns collection rights, including after Session replacement.
        recipient: Membership asked to handle the work.
        thread_id: Conversation for continuing with the same participants; omitted for unthreaded work.
        trace_id: Causal operation id usable with operator `get_trace`.
        created_at: Request acceptance time.
        updated_at: Last state transition or observation of a late reply.
        deadline: Work cutoff; a retained terminal Ticket stays terminal after this time.
        late_reply_count: Distinct replies observed after the Ticket became terminal.
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
    """Request completed by its first accepted successful reply.

    Attributes:
        response: Winning immutable response Message, including its envelope.
    """

    state: Literal["completed"]
    response: ResponseMessage

    @property
    def content(self) -> JsonValue:
        """Successful response content; may be JSON null. Other Ticket states have no content property."""
        return self.response.content


class FailedTicket(TicketBase):
    """Request ended by an agent or Runtime failure.

    The failure is returned data. It does not mean that collecting this Ticket
    raises an exception.
    """

    state: Literal["failed"]
    error: ErrorObject


class ExpiredTicket(TicketBase):
    """Request whose deadline passed before an accepted reply; carries a deadline-exceeded error."""

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


def parse_ticket(data: object) -> Ticket:
    """Parse a saved wire result, choosing the variant from `state`.

    An existing Ticket is returned unchanged.

    Raises:
        ValueError: Input is not an object or fails validation.
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
    """Failure code and requester-visible message, without wire error details or retry advice."""

    code: ErrorCode
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class TicketViewBase(SchemaModel):
    """The compact result returned to a model by Team tools.

    Branch on `state` before reading content or error. A completed view remains
    completed after its original deadline while the result is retained.

    Attributes:
        ticket_id: Request Message id to keep for `get_result`; wire Tickets use `id`.
        thread_id: Conversation to continue with the same participants, when present.
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
    """Successful reply content alone, without a response Message envelope."""

    state: Literal["completed"]
    content: JsonValue


class FailedTicketView(TicketViewBase):
    """Failed request with a compact error code and message."""

    state: Literal["failed"]
    error: TicketViewError


class ExpiredTicketView(TicketViewBase):
    """Expired request with a compact deadline-exceeded error."""

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


def parse_ticket_view(data: object) -> TicketView:
    """Parse a model-facing result, choosing the variant from `state`.

    An existing TicketView is returned unchanged.

    Raises:
        ValueError: Input is not an object or fails validation.
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
    """Return the model-facing projection of a wire Ticket.

    Uses `ticket_id` in place of `id`, returns completed content without its
    Message envelope, and keeps only code and message for failures. Wire timing,
    identity and trace fields are left out. Omitted Thread ids stay absent.
    """
    base: JsonObject = {"ticket_id": ticket.id}
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
