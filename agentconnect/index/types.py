"""Index registration enumerations and Capability.

These names belong to the published-directory Index, not the Team Runtime
vocabulary in ``core/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

__all__ = [
    "AgentType",
    "InteractionMode",
    "Capability",
]


class AgentType(str, Enum):
    """Kinds of Agent used by Index registration objects."""

    HUMAN = "human"
    AI = "ai"


class InteractionMode(str, Enum):
    """Declared interaction modes on Index registration objects."""

    HUMAN_TO_AGENT = "human_to_agent"
    AGENT_TO_AGENT = "agent_to_agent"


@dataclass
class Capability:
    """Named capability used by the Index directory implementation."""

    name: str
    description: str
    input_schema: Optional[Dict[str, str]] = None
    output_schema: Optional[Dict[str, str]] = None
    version: str = "1.0"
