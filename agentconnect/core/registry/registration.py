"""
Registration information for agents in the AgentConnect framework.

This module defines the AgentRegistration dataclass for storing the registration
information of agents in the system.
"""

# Standard library imports
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Absolute imports from agentconnect package
from agentconnect.core.types import (
    AgentIdentity,
    AgentType,
    Capability,
    InteractionMode,
    Skill,
)


@dataclass
class AgentRegistration:
    """
    Registration information for an agent.

    This class stores the complete registration information for an agent, including
    its identity, capabilities, skills, and metadata needed for discovery and interaction.

    Attributes:
        agent_id: Unique identifier for the agent
        agent_type: Type of agent (human, AI)
        interaction_modes: Supported interaction modes
        identity: Agent's decentralized identity
        name: Name of the agent
        summary: Brief summary of the agent's purpose
        description: Detailed description of the agent
        version: Version of the agent
        documentation_url: URL to the agent's documentation
        organization: Organization or entity providing the agent (e.g., 'Acme Corp', 'did:org:123').
                     Using a verifiable ID is recommended for robustness.
        developer: Individual or team that developed the agent (e.g., 'Alice', 'did:person:abc').
                  Using a verifiable ID is recommended.
        url: Endpoint URL for the agent
        auth_schemes: List of supported authentication schemes
        default_input_modes: List of supported input modes
        default_output_modes: List of supported output modes
        capabilities: List of capabilities the agent provides
        skills: List of skills the agent possesses
        examples: Example inputs/outputs or use cases
        tags: Keywords for filtering
        payment_address: Agent's primary wallet address for receiving payments
        custom_metadata: Additional custom metadata about the agent
        registered_at: When the agent was registered
    """

    agent_id: str
    agent_type: AgentType
    interaction_modes: list[InteractionMode]
    identity: AgentIdentity
    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    documentation_url: Optional[str] = None
    organization: Optional[str] = None  # Replaces organization_id
    developer: Optional[str] = None  # Replaces owner_id
    url: Optional[str] = None
    auth_schemes: List[str] = field(default_factory=list)
    default_input_modes: List[str] = field(default_factory=list)
    default_output_modes: List[str] = field(default_factory=list)
    capabilities: List[Capability] = field(default_factory=list)
    skills: List[Skill] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    payment_address: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)  # Replaces metadata
    registered_at: datetime = field(default_factory=datetime.now)
