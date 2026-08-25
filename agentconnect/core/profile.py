"""Discovery Profile and Skill value types.

A Profile describes what an Agent claims it can do. Identity, name, Address,
and routing data belong elsewhere. ``Capability`` remains for the current
directory implementation until discovery is rebuilt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agentconnect.core.types import AgentType


@dataclass
class Capability:
    """Named capability used by the current directory implementation."""

    name: str
    description: str
    input_schema: Optional[Dict[str, str]] = None
    output_schema: Optional[Dict[str, str]] = None
    version: str = "1.0"


class Skill(BaseModel):
    """One thing an Agent claims it can do, described in natural language."""

    name: str
    description: Optional[str] = None


class AgentProfile(BaseModel):
    """Discovery profile for an Agent.

    The current object still carries registration fields the directory uses
    (``agent_id``, ``agent_type``, ``capabilities``). Discovery-only fields are
    ``summary``, ``skills``, ``description``, and ``tags``.
    """

    agent_id: str
    agent_type: AgentType
    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    documentation_url: Optional[str] = None
    organization: Optional[str] = None
    developer: Optional[str] = None
    url: Optional[str] = None
    auth_schemes: List[str] = []
    default_input_modes: List[str] = []
    default_output_modes: List[str] = []
    capabilities: List[Capability] = []
    skills: List[Skill] = []
    examples: List[str] = []
    tags: List[str] = []
    payment_address: Optional[str] = None
    custom_metadata: Dict[str, Any] = {}
    reputation_score: Optional[float] = Field(None, exclude=True)
