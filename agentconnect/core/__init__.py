"""
Core components for the AgentConnect framework.

This module provides the foundational building blocks for agent-based systems, including:
- Agent identity and verification
- Message creation and validation
- Agent registration and discovery
- Type definitions and enumerations
"""

from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentType,
    Capability,
    AgentIdentity,
    InteractionMode,
    ModelProvider,
    ModelName,
)
from agentconnect.core.registry import AgentRegistry

__all__ = [
    # Message
    "Message",
    # Types
    "AgentType",
    "Capability",
    "AgentIdentity",
    "InteractionMode",
    "ModelProvider",
    "ModelName",
    # Registry
    "AgentRegistry",
]
