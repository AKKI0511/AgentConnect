"""Closed Message kinds.

Application-level typing belongs in Message ``content`` or ``metadata``, not in
an extra kind. Control events that used to have dedicated types store a
``control`` key in metadata.
"""

from enum import Enum


class MessageKind(str, Enum):
    """Closed set of Message kinds."""

    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    EVENT = "event"


CONTROL_STOP = "stop"
CONTROL_COOLDOWN = "cooldown"
CONTROL_SYSTEM = "system"
CONTROL_IGNORE = "ignore"
