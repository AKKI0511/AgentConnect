"""Immutable Message kinds and Delivery.

A handler receives a MailboxMessage (request or event) with attribute
access. Response and error Messages are created by the Runtime on reply.
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
    "RequestMessageBase",
    "NoReplyRequestMessage",
    "ReplyExpectedRequestMessage",
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
    """Fields shared by every accepted Message."""

    id: Uuid
    sender: QualifiedAddress
    recipient: QualifiedAddress
    created_at: Timestamp
    trace_id: Uuid
    thread_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None


class RequestMessageBase(MessageBase):
    """Fields shared by request Messages."""

    kind: Literal["request"] = "request"
    content: JsonValue
    metadata: Optional[JsonObject] = None


class NoReplyRequestMessage(RequestMessageBase):
    """Request that expects no reply and creates no Ticket."""


class ReplyExpectedRequestMessage(RequestMessageBase):
    """Request tracked by a Ticket until its deadline."""

    deadline: Timestamp


class EventMessage(MessageBase):
    """Information sent without a reply or Ticket."""

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


RequestMessage = Union[NoReplyRequestMessage, ReplyExpectedRequestMessage]
MailboxMessage = Union[RequestMessage, EventMessage]
Message = Union[RequestMessage, EventMessage, ResponseMessage, ErrorMessage]


class Delivery(SchemaModel):
    """One exclusive attempt to handle a Message."""

    lease_id: Uuid
    lease_expires_at: Timestamp
    attempt: int = Field(ge=1)
    message: Union[NoReplyRequestMessage, ReplyExpectedRequestMessage, EventMessage]
    history: list[Message]
    history_complete: bool


def is_reply_expected(message: Message) -> bool:
    """Return True when ``message`` is a reply-expected request."""
    return isinstance(message, ReplyExpectedRequestMessage)


def parse_message(data: Any, *, validate: bool = True) -> Message:
    """Parse a Message mapping. Overlapping request shapes use ``deadline``."""
    del validate
    if isinstance(
        data,
        (
            NoReplyRequestMessage,
            ReplyExpectedRequestMessage,
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
        cls: type[SchemaModel] = (
            ReplyExpectedRequestMessage if "deadline" in data else NoReplyRequestMessage
        )
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
