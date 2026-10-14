"""Public ErrorObject and deadline-exceeded failure."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from agentconnect.core.base import JsonObject, SchemaModel
from agentconnect.core.primitives import ErrorCode

__all__ = ["ErrorCode", "ErrorObject", "DeadlineExceededError"]


class ErrorObject(SchemaModel):
    """Public failure data shared by Runtime errors and handler failures.

    `code` is a well-known `ErrorCode`. An Agent application failure
    code belongs in `details` of a `handler_failed` error.

    Attributes:
        code: Closed public error code.
        message: Safe human-readable explanation.
        details: Optional structured data safe to reveal to the requester.
        retryable: Whether repeating the failed action may succeed
            without changing input. Omit when unknown.
    """

    code: ErrorCode
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    details: Optional[JsonObject] = None
    retryable: Optional[bool] = None


class DeadlineExceededError(ErrorObject):
    """Error stored by an expired Ticket.

    A Ticket is the requester's record for one request. When its
    deadline passes before an accepted reply, the Ticket is `expired`
    and carries this object. `code` is always `deadline_exceeded`.
    """

    code: Literal["deadline_exceeded"]
