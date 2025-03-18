"""
Core exceptions for the AgentConnect framework.

This module defines all core exceptions that can be raised by the framework.
Centralizing exceptions here helps avoid circular imports and makes the error
hierarchy clearer.
"""


class SecurityError(Exception):
    """
    Exception raised when message verification fails.

    This exception is raised when a message signature cannot be verified,
    indicating a potential security issue.
    """

    pass


class AgentError(Exception):
    """Base exception for agent-related errors."""

    pass


class RegistrationError(AgentError):
    """Exception raised when agent registration fails."""

    pass


class CommunicationError(AgentError):
    """Exception raised when agent communication fails."""

    pass


class CapabilityError(AgentError):
    """Exception raised when there's an issue with agent capabilities."""

    pass


class ConfigurationError(Exception):
    """Exception raised when there's an issue with configuration."""

    pass
