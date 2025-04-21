"""
Registration information for agents in the AgentConnect framework.

This module defines the AgentRegistration dataclass for storing the registration
information of agents in the system.
"""

# Standard library imports
from dataclasses import dataclass, field
from typing import Dict, Optional

# Absolute imports from agentconnect package
from agentconnect.core.types import (
    AgentIdentity,
    AgentType,
    Capability,
    InteractionMode,
)


@dataclass
class AgentRegistration:
    """
    Registration information for an agent.

    This class stores the registration information for an agent, including
    its identity, capabilities, and interaction modes.

    Attributes:
        agent_id: Unique identifier for the agent
        organization_id: ID of the organization the agent belongs to
        agent_type: Type of agent (human, AI)
        interaction_modes: Supported interaction modes
        capabilities: List of agent capabilities
        identity: Agent's decentralized identity
        owner_id: ID of the agent's owner
        payment_address: Agent's primary wallet address for receiving payments
        metadata: Additional information about the agent
    """

    agent_id: str
    organization_id: Optional[str]
    agent_type: AgentType
    interaction_modes: list[InteractionMode]
    capabilities: list[Capability]
    identity: AgentIdentity
    owner_id: Optional[str] = None
    payment_address: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
