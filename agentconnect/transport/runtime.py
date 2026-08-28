"""Runtime operations a Client uses to talk to a Team.

Session is a set of operations, not a wire format. In-process and HTTP
both implement this protocol so agent code does not change between them.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping, Optional, Protocol

from agentconnect.core.spec import SPEC_VERSION

__all__ = ["SPEC_VERSION", "RuntimeTransport", "TransportError"]


class TransportError(Exception):
    """A Runtime operation failed with a public error code.

    ``code`` matches the Runtime contract (for example ``not_found``,
    ``busy``, ``unavailable``). Callers should branch on ``code``.
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
    def from_error_object(cls, body: Mapping[str, Any]) -> "TransportError":
        """Build from a public ErrorObject mapping."""
        code = str(body.get("code") or "internal")
        message = str(body.get("message") or "Runtime operation failed")
        details = body.get("details")
        retryable = body.get("retryable")
        return cls(
            code,
            message,
            details=details if isinstance(details, dict) else None,
            retryable=bool(retryable) if isinstance(retryable, bool) else None,
        )


def wrap_runtime_error(exc: BaseException) -> TransportError:
    """Map a Runtime-side exception onto TransportError without importing team."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        message = getattr(exc, "message", None)
        if not isinstance(message, str) or not message:
            message = str(exc)
        return TransportError(
            code,
            message,
            details=getattr(exc, "details", None),
            retryable=getattr(exc, "retryable", None),
        )
    return TransportError("internal", str(exc) or "Runtime operation failed")


class RuntimeTransport(Protocol):
    """One Client connection to a Runtime.

    Implementations must not import ``agentconnect.agent``. In-process
    implementations must not import ``agentconnect.team``; they call methods
    on a duck-typed Runtime object supplied by the caller.
    """

    async def join(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Create or reconnect a Membership and open a Session."""

    async def join_challenge(self) -> dict[str, Any]:
        """Return a short-lived challenge used to prove Agent DID control."""

    async def disconnect(self, session_token: str) -> None:
        """Close this Session. Membership is retained."""

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Prove the Client still holds its Session."""

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept one request or event for one recipient."""

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """Pull available work from the Membership Mailbox."""

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Finish a Delivery without a response Message."""

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a reply-expected Delivery with a response or error."""

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return the current Ticket owned by the caller."""

    async def get_history(
        self,
        session_token: str,
        thread_id: str,
        *,
        before: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history."""

    async def find(
        self,
        session_token: str,
        query: str,
        *,
        limit: int = 10,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Search this Team's Directory."""

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry."""

    def events(self, session_token: str) -> AsyncIterator[dict[str, Any]]:
        """Yield RuntimeEvent values until the Session ends.

        ``work_available`` is a hint to call ``lease``. Unknown types are
        ignored by the Client. Correctness does not depend on this stream.
        """

    async def close(self) -> None:
        """Release transport resources. Does not disconnect the Session."""
