"""
Decentralized communication infrastructure for the AgentConnect framework.

This module provides tools for peer-to-peer agent communication and message routing.
It includes a message routing system that facilitates agent discovery and interaction
without centralized control of agent behavior.

Key components:

- CommunicationHub: Message routing and delivery system for peer-to-peer agent communication
"""

from agentconnect.communication.hub import CommunicationHub

__all__ = [
    "CommunicationHub",
]
