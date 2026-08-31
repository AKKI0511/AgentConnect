"""Shared enumerations that are not the public Message, Profile, or Address nouns.

Identity, Profile, and Message kinds live in their own modules. This module
re-exports them so existing ``core.types`` imports keep working.

Model choice is a string passed to LiteLLM. There is no provider enum.
"""

from __future__ import annotations

import importlib
from enum import Enum
from typing import Any


class AgentType(str, Enum):
    """Kinds of Agent used by older registration objects."""

    HUMAN = "human"
    AI = "ai"


class InteractionMode(str, Enum):
    """Declared interaction modes on older helper registration objects."""

    HUMAN_TO_AGENT = "human_to_agent"
    AGENT_TO_AGENT = "agent_to_agent"


class ProtocolVersion(str, Enum):
    """Legacy version labels. Not the public specification version."""

    V1_0 = "1.0"
    V1_1 = "1.1"


class NetworkMode(str, Enum):
    """Legacy network-mode labels. Unused by the Team Runtime."""

    STANDALONE = "standalone"
    NETWORKED = "networked"


_LAZY_EXPORTS = {
    "AgentIdentity": ("agentconnect.core.identity", "AgentIdentity"),
    "AgentMetadata": ("agentconnect.core.identity", "AgentMetadata"),
    "VerificationStatus": ("agentconnect.core.identity", "VerificationStatus"),
    "AgentProfile": ("agentconnect.core.profile", "AgentProfile"),
    "Capability": ("agentconnect.core.profile", "Capability"),
    "Skill": ("agentconnect.core.profile", "Skill"),
    "MessageKind": ("agentconnect.core.kinds", "MessageKind"),
}

__all__ = [
    "AgentType",
    "InteractionMode",
    "ProtocolVersion",
    "NetworkMode",
    *sorted(_LAZY_EXPORTS),
]


def __getattr__(name: str) -> Any:
    """Load identity, profile, and kind types without an import cycle."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    return getattr(importlib.import_module(module_name), attr)
