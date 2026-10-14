"""Immutable Message kinds and Delivery.

A handler receives a `MailboxMessage` (request or event) with attribute
access. A request always expects a reply and opens a Ticket, the
requester's durable record for that work. Fire-and-forget work is an
event. Response and error Messages are created by the Runtime on reply.

Examples:
    Read fields on a delivered Message:

    ```python
    msg.kind
    msg.content
    msg.sender_did
    msg.deadline  # requests only
    msg.seq  # present when the Message belongs to a Thread
    ```
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, Union

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from agentconnect.core.base import (
    JsonInt,
    JsonObject,
    JsonValue,
    SchemaModel,
    validation_message,
)
from agentconnect.core.error import ErrorObject
from agentconnect.core.primitives import AgentDid, QualifiedAddress, Timestamp, Uuid

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

    `id` is Client-proposed on `send` and `reply` and stored unchanged at
    acceptance. The Runtime sets canonical Addresses (`name@team`),
    `sender_did` (the sender's `did:key`), `created_at`, `trace_id`, and
    `seq` when `thread_id` is present. `seq` is present exactly when
    `thread_id` is present. History and `before` cursors order by `seq`,
    not by `created_at`.

    Attributes:
        id: Immutable Message id and idempotency key.
        sender: Canonical qualified Address set by the Runtime.
        sender_did: Verified DID of the sending Membership, copied from
            the Session at acceptance.
        recipient: Canonical qualified Address set by the Runtime.
        created_at: Runtime acceptance time.
        trace_id: Correlation id for one causal operation.
        thread_id: Conversation grouping id, when the Message has one.
        parent_id: Message this one replies to or continues.
        seq: Position in the Thread, assigned on acceptance. Present
            exactly when `thread_id` is present. First Message is `1`.
    """

    id: Uuid
    sender: QualifiedAddress
    sender_did: AgentDid
    recipient: QualifiedAddress
    created_at: Timestamp
    trace_id: Uuid
    thread_id: Optional[Uuid] = None
    parent_id: Optional[Uuid] = None
    seq: Optional[JsonInt] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def thread_id_and_seq_together(self) -> MessageBase:
        """Reject a Message that has only one of `thread_id` and `seq`."""
        if (self.thread_id is None) != (self.seq is None):
            raise ValueError("seq is present exactly when thread_id is present")
        return self


class RequestMessage(MessageBase):
    """Request that always expects a reply and opens a Ticket.

    `deadline` is required on an accepted request. Fire-and-forget work
    is an `event`. A Ticket is the requester's durable record whose id
    equals this Message id.

    Attributes:
        kind: Always `request`.
        content: Sender-controlled work input.
        metadata: Sender-controlled application data. Never used for
            Runtime decisions.
        deadline: Absolute time after which an open Ticket expires.

    Examples:
        ```python
        msg.kind  # "request"
        msg.deadline
        msg.seq  # set when the Message belongs to a Thread
        ```
    """

    kind: Literal["request"]
    content: JsonValue
    metadata: Optional[JsonObject] = None
    deadline: Timestamp


class EventMessage(MessageBase):
    """Information sent without a reply or Ticket.

    Attributes:
        kind: Always `event`.
        content: Sender-controlled event data.
        metadata: Sender-controlled application data. Never used for
            Runtime decisions.

    Examples:
        ```python
        await agent.tell("writer", {"note": "source changed"})
        ```
    """

    kind: Literal["event"]
    content: JsonValue
    metadata: Optional[JsonObject] = None


class ResponseMessage(MessageBase):
    """Successful reply created by the Runtime.

    Attributes:
        kind: Always `response`.
        content: Successful application result. May be JSON null.
        parent_id: Request Message id this reply answers.
    """

    kind: Literal["response"]
    content: JsonValue
    parent_id: Uuid


class ErrorMessage(MessageBase):
    """Failed reply created by the Runtime.

    Attributes:
        kind: Always `error`.
        error: Safe failure returned to the requester.
        parent_id: Request Message id this error answers.
    """

    kind: Literal["error"]
    error: ErrorObject
    parent_id: Uuid


MailboxMessage = Union[RequestMessage, EventMessage]
"""Request or event a handler receives. A request expects a reply; an event does not."""
Message = Union[RequestMessage, EventMessage, ResponseMessage, ErrorMessage]
"""Immutable Message stored by the Runtime."""


class Delivery(SchemaModel):
    """One exclusive attempt to handle a Message.

    `history` is the bounded recent Thread window, ordered by `seq` and
    excluding `message`. After `join(..., delivery_history="ids")`,
    `history` is empty and `history_ids` lists those earlier ids.

    Attributes:
        lease_id: Opaque id authorizing completion of this attempt.
        lease_expires_at: Time after which this attempt is no longer active.
        attempt: Starts at 1 and increases after recovery.
        message: Request or event leased from the Membership's Mailbox.
        history: Bounded recent window of earlier Messages. Empty when
            the Session joined with `delivery_history="ids"`.
        history_ids: Earlier Message ids when the Session joined with
            `delivery_history="ids"`. Omitted when the window is bodies.
        history_complete: True when the delivered window already contains
            every earlier retained Message.

    Examples:
        ```python
        delivery.history
        delivery.history_ids  # present only for ids mode
        delivery.history_complete
        ```
    """

    lease_id: Uuid
    lease_expires_at: Timestamp
    attempt: JsonInt = Field(ge=1)
    message: Union[RequestMessage, EventMessage]
    history: list[Message]
    history_ids: Optional[list[Uuid]] = None
    history_complete: bool


def is_reply_expected(message: Message) -> bool:
    """Return True when `message` is a request.

    Every request expects a reply. An event does not.

    Args:
        message: Any stored Message kind.

    Returns:
        True for a `RequestMessage`, False otherwise.
    """
    return isinstance(message, RequestMessage)


def parse_message(data: Any) -> Message:
    """Parse a Message mapping. A request requires `deadline`.

    Args:
        data: JSON object, or an already parsed Message instance.

    Returns:
        A frozen request, event, response, or error Message.

    Raises:
        ValueError: `data` is not an object, `kind` is unknown, or
            validation fails.
    """
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
    try:
        if kind == "request":
            return RequestMessage.model_validate(data)
        if kind == "event":
            return EventMessage.model_validate(data)
        if kind == "response":
            return ResponseMessage.model_validate(data)
        if kind == "error":
            return ErrorMessage.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc
    raise ValueError("kind must be request, event, response, or error")


def parse_delivery(data: Any) -> Delivery:
    """Parse a Delivery, including nested Messages.

    Args:
        data: JSON object, or an already parsed `Delivery`.

    Returns:
        A frozen Delivery with nested Messages parsed.

    Raises:
        ValueError: `data` is not an object, `history` is not an array,
            or nested validation fails.
    """
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


MESSAGE_ADAPTER: TypeAdapter[Message] = TypeAdapter(Message)
MAILBOX_MESSAGE_ADAPTER: TypeAdapter[MailboxMessage] = TypeAdapter(MailboxMessage)
