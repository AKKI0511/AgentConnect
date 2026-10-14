"""Published v0.4 compatibility until v1.0.

New code imports Team files from `agentconnect.config`, schema types
from `agentconnect.core`, and errors from `SessionError` or `TeamError`.
This package is the only supported home for YAML Team files and the
v0.4 exception names (`AgentError`, `CommunicationError`, and the
others re-exported here).

A v0.4 `agentconnect.yaml` still loads through this package when no
TOML Team file exists in this directory or any ancestor. Do not add
new callers here.
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
