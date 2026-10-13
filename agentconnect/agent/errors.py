"""Errors raised by the agent Session client.

Catch `SessionError` on join, send, Directory, and delivery-finish
calls. `code` is a public Runtime error code. Branch on `code`, not on
the exception message.

Examples:
    After `join`, branch on `code` when a send fails:

    ```python
    from agentconnect import SessionError

    try:
        await agent.ask("writer", {"task": "draft this"})
    except SessionError as exc:
        print(exc.code, exc.message)
    ```
"""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.transport.runtime import TransportError


class SessionError(Exception):
    """A Session or handler-facing Runtime operation failed.

    `code` is a public Runtime error code such as `unauthorized`,
    `invalid_request`, or `not_found`. Branch on `code`, not on the
    exception message.

    Attributes:
        code: Public Runtime error code.
        message: Human-readable explanation.
        details: Optional JSON object with more data.
        retryable: Whether the caller may retry the same operation, when
            the Runtime said so. `None` means unspecified.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        """Record the public error `code` and human-readable `message`.

        Args:
            code: Public Runtime error code.
            message: Human-readable explanation.
            details: Optional JSON object with more data.
            retryable: Whether the caller may retry the same operation.
        """
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable

    @classmethod
    def from_transport(cls, exc: TransportError) -> "SessionError":
        """Wrap a transport failure for agent-facing callers.

        Session methods already do this. Application code usually
        catches `SessionError` rather than constructing it.

        Args:
            exc: Failure raised by the Session transport.

        Returns:
            A `SessionError` with the same `code`, `message`, `details`,
            and `retryable` flag.
        """
        return cls(
            exc.code,
            exc.message,
            details=exc.details,
            retryable=exc.retryable,
        )
