"""Message kinds that distinguish requests, events and replies."""

from enum import Enum


class MessageKind(str, Enum):
    """Kinds of accepted Message.

    Requests expect a reply and open a Ticket. Events do neither. The Runtime
    creates response or error Messages when a request is answered. Application
    categories belong in content or metadata.
    """

    REQUEST = "request"
    """Work that expects a reply."""
    RESPONSE = "response"
    """Successful reply to a request."""
    ERROR = "error"
    """Failed reply to a request."""
    EVENT = "event"
    """Information sent without a reply or Ticket."""
