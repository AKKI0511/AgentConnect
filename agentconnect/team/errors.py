"""Public error raised by a failed Runtime operation."""

from __future__ import annotations

from typing import Any, Optional


class TeamError(Exception):
    """A Runtime operation failed with a public error code.

    ``code`` is one of the well-known codes in the AgentConnect Runtime
    contract (for example ``not_found``, ``busy``, ``id_conflict``). Callers
    should branch on ``code``, not on the exception message.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        """Set the public ``code`` and ``message`` for this failure."""
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable

    def to_error_object(self) -> dict[str, Any]:
        """Return the public ErrorObject for this failure."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        if self.retryable is not None:
            error["retryable"] = self.retryable
        return error
