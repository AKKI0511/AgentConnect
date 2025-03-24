"""
Core components for the AgentConnect framework.

This module provides the foundational building blocks for agent-based systems in the
decentralized AgentConnect framework, including:

- **Base Agent**: Abstract base class for all agent implementations
- **Message Handling**: Secure, signed message creation and verification
- **Agent Identity**: Decentralized identity and cryptographic verification
- **Capability Registry**: Dynamic discovery of agent capabilities
- **Type System**: Rich type definitions for the entire framework

The core module focuses on establishing the foundation for decentralized agent interaction
without imposing centralized control structures.
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

# Define public API
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
