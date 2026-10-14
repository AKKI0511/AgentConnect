"""Closed Message kinds.

`kind` is one of `request`, `event`, `response`, or `error`. Put
application-level typing in Message `content` or `metadata`.
"""

from enum import Enum


class MessageKind(str, Enum):
    """Closed set of Message kinds.

    A request always expects a reply and opens a Ticket, the requester's
    durable record for that work. An event does not. Response and error
    Messages are created by the Runtime on reply.

    Attributes:
        REQUEST: Work that expects a reply.
        RESPONSE: Successful reply to a request.
        ERROR: Failed reply to a request.
        EVENT: Information sent without a reply or Ticket.
    """

    REQUEST = "request"
    """Work that expects a reply."""
    RESPONSE = "response"
    """Successful reply to a request."""
    ERROR = "error"
    """Failed reply to a request."""
    EVENT = "event"
    """Information sent without a reply or Ticket."""
