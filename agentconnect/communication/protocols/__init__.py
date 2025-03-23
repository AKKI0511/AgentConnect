"""
Communication protocols that enable diverse agent interactions.

This module provides protocol implementations that standardize different types of
agent communication patterns. These protocols support peer-to-peer messaging,
capability discovery, and collaborative task execution between independent agents.

The protocols ensure message format consistency while allowing agents to maintain
their individual autonomy and decision-making processes.
"""

from agentconnect.communication.protocols.agent import SimpleAgentProtocol
from agentconnect.communication.protocols.base import BaseProtocol
from agentconnect.communication.protocols.collaboration import CollaborationProtocol

__all__ = ["BaseProtocol", "SimpleAgentProtocol", "CollaborationProtocol"]
