"""Re-exports of public schema primitives and the Profile and Message kinds.

Identity types load from ``agentconnect.core.identity``.
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
    """Load identity types without an import cycle."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    return getattr(importlib.import_module(module_name), attr)
