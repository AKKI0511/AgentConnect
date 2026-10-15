"""Accepted Messages and the Delivery attempts used to handle them.

Handlers receive requests and events. A request opens a requester-owned
Ticket; an event expects no reply. Response and error Messages resolve
Tickets and appear in retained history, rather than the requester's Mailbox.
"""

from __future__ import annotations

from typing import Literal, Mapping, Optional, Union

from pydantic import Field, ValidationError, model_validator

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
    """Accepted work that expects a reply and opens a Ticket with this Message's id.

    The Runtime stamps the effective deadline at acceptance, including an
    inherited deadline when the send omitted one.

    Attributes:
        content: Sender's work input; may be any JSON value, including null.
        metadata: Application data that does not control Runtime decisions.
        deadline: Work cutoff after which an open Ticket expires.
    """

    kind: Literal["request"]
    content: JsonValue
    metadata: Optional[JsonObject] = None
    deadline: Timestamp


class EventMessage(MessageBase):
    """Accepted information that expects no reply and opens no Ticket.

    Attributes:
        metadata: Application data that does not control Runtime decisions.
    """

    kind: Literal["event"]
    content: JsonValue
    metadata: Optional[JsonObject] = None


class ResponseMessage(MessageBase):
    """Successful reply stored by the Runtime.

    Attributes:
        content: Application result; JSON null is a successful answer too.
        parent_id: Request Message id this reply answers.
    """

    kind: Literal["response"]
    content: JsonValue
    parent_id: Uuid


class ErrorMessage(MessageBase):
    """Failed reply stored by the Runtime.

    Attributes:
        error: Failure information safe to reveal to the requester.
        parent_id: Request Message id this failure answers.
    """

    kind: Literal["error"]
    error: ErrorObject
    parent_id: Uuid


MailboxMessage = Union[RequestMessage, EventMessage]
"""Request or event a handler receives. A request expects a reply; an event does not."""
Message = Union[RequestMessage, EventMessage, ResponseMessage, ErrorMessage]
"""Immutable Message stored by the Runtime."""


class Delivery(SchemaModel):
    """An exclusive leased attempt to handle a request or event.

    The Message stays the same across retries; each recovered attempt has its
    own lease. Completion and reply require the active lease held by this Session.

    Attributes:
        lease_id: Authorizes this attempt's renewal, completion or reply.
        lease_expires_at: After this time the attempt is no longer active.
        attempt: Starts at one and increases after recovery.
        history: Recent earlier Thread Messages in ascending `seq` order,
            excluding the delivered Message. Empty in `delivery_history="ids"` mode.
        history_ids: Earlier Message ids in ids mode; omitted in bodies mode.
        history_complete: Whether the window includes every earlier retained Message.
            Use Thread history paging when you need more.
    """

    lease_id: Uuid
    lease_expires_at: Timestamp
    attempt: JsonInt = Field(ge=1)
    message: Union[RequestMessage, EventMessage]
    history: list[Message]
    history_ids: Optional[list[Uuid]] = None
    history_complete: bool


def is_reply_expected(message: Message) -> bool:
    """Return whether the Message is a request and therefore expects a reply."""
    return isinstance(message, RequestMessage)


def parse_message(data: object) -> Message:
    """Parse a Message mapping. A request requires `deadline`.

    Args:
        data: JSON object, or an already parsed Message instance.

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


def parse_delivery(data: object) -> Delivery:
    """Parse a Delivery, including nested Messages.

    Args:
        data: JSON object, or an already parsed `Delivery`.

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
