"""
Agent registry for the AgentConnect framework.

This module provides the AgentRegistry class for agent registration, discovery,
and capability matching, as well as the AgentRegistration dataclass for storing
agent registration information.
"""

from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.registry.registry_base import AgentRegistry
from agentconnect.core.registry.capability_discovery import CapabilityDiscoveryService

# Define public API
__all__ = ["AgentRegistry", "AgentRegistration", "CapabilityDiscoveryService"]
