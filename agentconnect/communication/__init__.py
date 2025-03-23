"""
Decentralized communication infrastructure for the AgentConnect framework.

This module provides tools for peer-to-peer agent communication, message routing, and protocol handling.
It includes a message routing system that facilitates agent discovery and interaction without
centralized control of agent behavior.

Key components:
- CommunicationHub: Message routing and delivery system for peer-to-peer agent communication
- Protocol implementations: Base protocol and specialized variants for different interaction types
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
