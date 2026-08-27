"""Core nouns: Message, Address, identity, Profile, kinds, and errors.

This package has no I/O and imports no sibling AgentConnect packages.
"""

from agentconnect.core.address import (
    ADDRESS_OUTSIDE_TEAM,
    INVALID_ADDRESS,
    ParsedAddress,
    parse_address,
    parse_agent_name,
    parse_team_name,
    resolve_address,
)
from agentconnect.core.exceptions import (
    AgentError,
    CapabilityError,
    CommunicationError,
    ConfigurationError,
    RegistrationError,
    SecurityError,
)
from agentconnect.core.identity import AgentIdentity, AgentMetadata, VerificationStatus
from agentconnect.core.kinds import (
    CONTROL_COOLDOWN,
    CONTROL_IGNORE,
    CONTROL_STOP,
    CONTROL_SYSTEM,
    MessageKind,
)
from agentconnect.core.message import Message
from agentconnect.core.profile import (
    AgentProfile,
    Capability,
    Skill,
    validate_discovery_profile,
)
from agentconnect.core.spec import SPEC_VERSION
from agentconnect.core.types import (
    AgentType,
    InteractionMode,
    ModelName,
    ModelProvider,
    NetworkMode,
    ProtocolVersion,
)

__all__ = [
    "ADDRESS_OUTSIDE_TEAM",
    "INVALID_ADDRESS",
    "ParsedAddress",
    "parse_address",
    "parse_agent_name",
    "parse_team_name",
    "resolve_address",
    "AgentError",
    "CapabilityError",
    "CommunicationError",
    "ConfigurationError",
    "RegistrationError",
    "SecurityError",
    "AgentIdentity",
    "AgentMetadata",
    "VerificationStatus",
    "CONTROL_COOLDOWN",
    "CONTROL_IGNORE",
    "CONTROL_STOP",
    "CONTROL_SYSTEM",
    "MessageKind",
    "Message",
    "AgentProfile",
    "Capability",
    "Skill",
    "validate_discovery_profile",
    "SPEC_VERSION",
    "AgentType",
    "InteractionMode",
    "ModelName",
    "ModelProvider",
    "NetworkMode",
    "ProtocolVersion",
]
