"""
Communication infrastructure for the AgentConnect framework.

This module provides tools for agent communication, message routing, and protocol handling.
It includes the CommunicationHub for message routing and various protocol implementations.

Key components:
- CommunicationHub: Central message routing and delivery system
- Protocol implementations: Base protocol and specialized variants
"""

from agentconnect.communication.hub import CommunicationHub
from agentconnect.communication.protocols.agent import SimpleAgentProtocol
from agentconnect.communication.protocols.base import BaseProtocol
from agentconnect.communication.protocols.collaboration import CollaborationProtocol

__all__ = [
    "CommunicationHub",
    "BaseProtocol",
    "SimpleAgentProtocol",
    "CollaborationProtocol",
]
