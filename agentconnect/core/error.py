"""Failure data returned by Runtime operations and request results."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from agentconnect.core.base import JsonObject, SchemaModel
from agentconnect.core.primitives import ErrorCode

__all__ = ["ErrorCode", "ErrorObject", "DeadlineExceededError"]


class ErrorObject(SchemaModel):
    """Failure information safe to reveal to a caller.

    A failed or expired Ticket carries this data; a rejected SDK operation
    raises an exception carrying a public code. Application-specific failure
    codes belong in `details` of a `handler_failed` error.

    Attributes:
        message: Explanation safe to show the requester.
        details: Structured data safe to reveal to the requester.
        retryable: Whether the same action may succeed without changing input;
            omission means the Runtime has not supplied retry advice.
    """

    code: ErrorCode
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    details: Optional[JsonObject] = None
    retryable: Optional[bool] = None


class DeadlineExceededError(ErrorObject):
    """Failure stored when an open Ticket reaches its work deadline."""

    code: Literal["deadline_exceeded"]
