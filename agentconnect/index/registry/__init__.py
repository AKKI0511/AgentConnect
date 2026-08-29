"""Published-directory registry used by the optional Index service.

This package is the Index's agent roster and vector search, not a Team's
local Directory. Team discovery lives in ``agentconnect.team.directory``.
"""

from agentconnect.index.registry.registration import AgentRegistration
from agentconnect.index.registry.registry_base import AgentRegistry
from agentconnect.index.registry.capability_discovery import CapabilityDiscoveryService

__all__ = ["AgentRegistry", "AgentRegistration", "CapabilityDiscoveryService"]
