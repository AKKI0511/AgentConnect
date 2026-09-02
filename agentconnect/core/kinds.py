"""Closed Message kinds.

Application-level typing belongs in Message ``content`` or ``metadata``.
"""

from enum import Enum


class MessageKind(str, Enum):
    """Closed set of Message kinds."""

    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    EVENT = "event"
