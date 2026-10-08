"""v0.4 ``agentconnect.core.types`` names, forwarded to current modules.

Import schema types from ``agentconnect.core`` in new code. This module
does not restore removed enumerations such as ``ModelProvider``.
"""

from __future__ import annotations

import importlib
from typing import Any

from agentconnect.core.kinds import MessageKind
from agentconnect.core.primitives import (
    CollectMode,
    DeliveryHistoryForm,
    ErrorCode,
    PersistenceMode,
    TicketState,
)
from agentconnect.core.profile import AgentProfile, Skill

_LAZY_EXPORTS = {
    "AgentIdentity": ("agentconnect.core.identity", "AgentIdentity"),
    "VerificationStatus": ("agentconnect.core.identity", "VerificationStatus"),
}

__all__ = [
    "AgentProfile",
    "Skill",
    "MessageKind",
    "CollectMode",
    "DeliveryHistoryForm",
    "ErrorCode",
    "PersistenceMode",
    "TicketState",
    *sorted(_LAZY_EXPORTS),
]


def __getattr__(name: str) -> Any:
    """Load identity types without importing cryptography at module import."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    return getattr(importlib.import_module(module_name), attr)
