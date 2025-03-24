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
from agentconnect.communication import protocols

__all__ = [
    "CommunicationHub",
    "protocols",
]
