"""The error raised when a Team operation fails."""

from __future__ import annotations

from typing import Any, Optional

IDENTITY_MISSING = (
    "Stored Team state is missing Membership identity. "
    "Reset this Team's store before using this Runtime."
)


class TeamError(Exception):
    """A failed Team operation.

    Read `code` to decide whether to handle or propagate the error.

    Common codes are `not_found`, `unauthorized`, `busy`, and
    `wait_limit`.

    Examples:
        `team` is started, and `name` is an agent name. Removing a
        membership that is already gone is safe. Any other `TeamError`
        still propagates.

        ```python
        from agentconnect.team import TeamError

        try:
            await team.remove_membership(name)
        except TeamError as exc:
            if exc.code != "not_found":
                raise
        ```
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code: str = code
        """Machine-readable failure code."""
        self.message: str = message
        """Explanation of the failure for a person."""
        self.details: Optional[dict[str, Any]] = details
        """Additional error fields, or None when unspecified."""
        self.retryable: Optional[bool] = retryable
        """Whether the same call may succeed later, or None when unspecified."""

    def to_error_object(self) -> dict[str, Any]:
        """Serialize this error for a Runtime response.

        Includes `code` and `message`; `details` and `retryable` are omitted
        when None.
        """
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        if self.retryable is not None:
            error["retryable"] = self.retryable
        return error
