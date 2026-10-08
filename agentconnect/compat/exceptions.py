"""v0.4 exception names kept until v1.0.

Prefer ``SessionError`` and ``TeamError`` in new code.
"""


class SecurityError(Exception):
    """Raised when a signed collaboration message cannot be verified."""


class AgentError(Exception):
    """Base class for v0.4 agent errors."""


class RegistrationError(AgentError):
    """Raised when Index registration fails."""


class CommunicationError(AgentError):
    """Raised when v0.4 agent communication fails."""


class CapabilityError(AgentError):
    """Raised when an Index capability record is unusable."""


class ConfigurationError(Exception):
    """Raised when v0.4 SDK settings cannot be loaded."""
