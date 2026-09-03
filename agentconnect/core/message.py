"""Immutable Message kinds and Delivery.

A handler receives a MailboxMessage (request or event) with attribute
access. A request always expects a reply. Fire-and-forget work is an
event. Response and error Messages are created by the Runtime on reply.

    msg.kind
    msg.content
    msg.deadline   # requests only
    msg.seq        # present when the Message belongs to a Thread
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError

from agentconnect.core.base import (
    JsonObject,
    JsonValue,
    SchemaModel,
    validation_message,
)
from agentconnect.core.error import ErrorObject
from agentconnect.core.primitives import QualifiedAddress, Timestamp, Uuid

__all__ = [
    "MessageBase",
    "RequestMessage",
    "EventMessage",
    "MailboxMessage",
    "ResponseMessage",
    "ErrorMessage",
    "Message",
    "Delivery",
    "parse_message",
    "parse_delivery",
    "is_reply_expected",
]


class MessageBase(SchemaModel):
    """Fields shared by every accepted Message.

    ``seq`` is present exactly when ``thread_id`` is present. History
    and ``before`` cursors order by ``seq``, not by ``created_at``.
    """

    id: Uuid
    sender: QualifiedAddress
    recipient: QualifiedAddress
    created_at: Timestamp
    trace_id: Uuid
    thread_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None
    seq: Optional[int] = Field(default=None, ge=1)


class RequestMessage(MessageBase):
    """Request that always expects a reply and opens a Ticket.

    ``deadline`` is required. Fire-and-forget work is an ``event``.

        msg.kind      # "request"
        msg.deadline
        msg.seq       # set when the Message belongs to a Thread
    """

    kind: Literal["request"] = "request"
    content: JsonValue
    metadata: Optional[JsonObject] = None
    deadline: Timestamp


class EventMessage(MessageBase):
    """Information sent without a reply or Ticket.

    await agent.tell("writer", {"note": "source changed"})
    """

    kind: Literal["event"] = "event"
    content: JsonValue
    metadata: Optional[JsonObject] = None


class ResponseMessage(MessageBase):
    """Successful reply created by the Runtime."""

    kind: Literal["response"] = "response"
    content: JsonValue
    parent_id: Uuid


class ErrorMessage(MessageBase):
    """Failed reply created by the Runtime."""

    kind: Literal["error"] = "error"
    error: ErrorObject
    parent_id: Uuid


MailboxMessage = Union[RequestMessage, EventMessage]
Message = Union[RequestMessage, EventMessage, ResponseMessage, ErrorMessage]


class Delivery(SchemaModel):
    """One exclusive attempt to handle a Message.

    ``history`` is the bounded recent Thread window, ordered by ``seq``
    and excluding ``message``.
    """

    lease_id: Uuid
    lease_expires_at: Timestamp
    attempt: int = Field(ge=1)
    message: Union[RequestMessage, EventMessage]
    history: list[Message]
    history_complete: bool


def is_reply_expected(message: Message) -> bool:
    """Return True when ``message`` is a request.

    Every request expects a reply. An event does not.
    """
    return isinstance(message, RequestMessage)


def parse_message(data: Any, *, validate: bool = True) -> Message:
    """Parse a Message mapping. A request requires ``deadline``."""
    del validate
    if isinstance(
        data,
        (
            RequestMessage,
            EventMessage,
            ResponseMessage,
            ErrorMessage,
        ),
    ):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("message must be an object")
    kind = data.get("kind")
    if kind == "request":
        cls: type[SchemaModel] = RequestMessage
    elif kind == "event":
        cls = EventMessage
    elif kind == "response":
        cls = ResponseMessage
    elif kind == "error":
        cls = ErrorMessage
    else:
        raise ValueError("kind must be request, event, response, or error")
    try:
        return cls.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def parse_delivery(data: Any, *, validate: bool = True) -> Delivery:
    """Parse a Delivery, including nested Messages."""
    del validate
    if isinstance(data, Delivery):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("delivery must be an object")
    body = dict(data)
    body["message"] = parse_message(body.get("message"))
    history = body.get("history") or []
    if not isinstance(history, list):
        raise ValueError("history must be an array")
    body["history"] = [parse_message(item) for item in history]
    try:
        return Delivery.model_validate(body)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


MESSAGE_ADAPTER = TypeAdapter(Message)
MAILBOX_MESSAGE_ADAPTER = TypeAdapter(MailboxMessage)
