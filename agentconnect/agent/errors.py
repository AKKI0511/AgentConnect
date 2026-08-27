"""Errors raised by the agent Session client."""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.transport.runtime import TransportError


class SessionError(Exception):
    """A Session or handler-facing Runtime operation failed.

    ``code`` is a public Runtime error code. Branch on ``code``, not on
    the exception message.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        """Record the public error ``code`` and human-readable ``message``."""
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable

    @classmethod
    def from_transport(cls, exc: TransportError) -> "SessionError":
        """Wrap a transport failure for agent-facing callers."""
        return cls(
            exc.code,
            exc.message,
            details=exc.details,
            retryable=exc.retryable,
        )
