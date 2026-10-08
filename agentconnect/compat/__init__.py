"""Published v0.4 compatibility until v1.0.

New code should import Team files from ``agentconnect.config``, schema
types from ``agentconnect.core``, and errors from ``SessionError`` or
``TeamError``. This package is the only place that still reads YAML Team
files and keeps the v0.4 exception and ``core.types`` names.
"""

from agentconnect.compat.exceptions import (
    AgentError,
    CapabilityError,
    CommunicationError,
    ConfigurationError,
    RegistrationError,
    SecurityError,
)

__all__ = [
    "AgentError",
    "CapabilityError",
    "CommunicationError",
    "ConfigurationError",
    "RegistrationError",
    "SecurityError",
]
