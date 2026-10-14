"""Runtime operations a Client uses to talk to a Team.

Session is a set of operations, not a wire format. In-process and HTTP
both implement this protocol so Agent code does not change between them.
Everyday Agent code uses `BaseAgent`, which calls these operations through
a Session transport.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping, Optional, Protocol

from agentconnect.core.spec import SPEC_VERSION

__all__ = ["SPEC_VERSION", "RuntimeTransport", "TransportError"]


class TransportError(Exception):
    """A Runtime operation failed with a public error code.

    `code` matches the Runtime contract (for example `not_found`,
    `busy`, `unavailable`). Branch on `code`, not on the exception
    message.

    Attributes:
        code: Public error code.
        message: Human-readable explanation.
        details: Optional extra fields from the Runtime.
        retryable: True when a later identical call may succeed.
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
            code: Public error code from the Runtime contract.
            message: Human-readable explanation.
            details: Optional extra fields.
            retryable: True when a later identical call may succeed.
        """
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable

    @classmethod
    def from_error_object(cls, body: Mapping[str, Any]) -> "TransportError":
        """Build from a public ErrorObject mapping.

        Args:
            body: Mapping with `code` and `message`.
        """
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
    """Map a Runtime-side exception onto `TransportError` without importing team.

    Args:
        exc: Exception raised by an in-process Runtime call.

    Returns:
        A `TransportError`. Uses `exc.code` when present, otherwise
        `internal`.
    """
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

    These token-taking methods are the Session transport. Everyday Agent
    code uses `BaseAgent`, not these methods directly. Implementations
    must not import `agentconnect.agent`. In-process implementations must
    not import `agentconnect.team`; they call methods on a duck-typed
    Runtime object supplied by the caller.
    """

    async def join(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Create or reconnect a Membership and open a Session.

        Args:
            request: Join body (`name`, `agent_did`, `profile`, …).
        """

    async def join_challenge(self) -> dict[str, Any]:
        """Return a short-lived challenge used to prove Agent DID control."""

    async def disconnect(self, session_token: str) -> None:
        """Close this Session. Membership is retained.

        Args:
            session_token: Live Session token from `join`.
        """

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Prove the Client still holds its Session and extend expiry.

        Args:
            session_token: Live Session token from `join`.
        """

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept one request or event for one recipient.

        Session transport. Agent code uses `BaseAgent.ask`.

        Args:
            session_token: Live Session token from `join`.
            request: Send body (`id`, `recipient`, `kind`, `content`, …).
        """

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """Pull available work from the Membership Mailbox.

        Args:
            session_token: Live Session token from `join`.
            max_items: How many Deliveries to take, 1 to 100.
        """

    async def renew(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Extend one active Delivery lease owned by this Session.

        Args:
            session_token: Live Session token from `join`.
            lease_id: `lease_id` from a Delivery this Session holds.
        """

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Finish a Delivery without a response Message.

        Args:
            session_token: Live Session token from `join`.
            lease_id: `lease_id` from a Delivery this Session holds.
        """

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a reply-expected Delivery with a response or error.

        Args:
            session_token: Live Session token from `join`.
            request: Reply body (`id`, `lease_id`, `outcome`, …).
        """

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return the current Ticket owned by the caller.

        Args:
            session_token: Live Session token from `join`.
            ticket_id: Ticket id from a request this Membership sent.
        """

    async def get_history(
        self,
        session_token: str,
        thread_id: str,
        *,
        before: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history.

        Args:
            session_token: Live Session token from `join`.
            thread_id: Thread id from a Message or Ticket.
            before: Return Messages older than this id. Omit for the
                newest page.
            limit: Page size from 1 to 200. Defaults to 50.
        """

    async def find(
        self,
        session_token: str,
        query: str,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search this Team's Directory.

        Args:
            session_token: Live Session token from `join`.
            query: Natural-language need.
            limit: Maximum matches from 1 to 100. Omit for every other
                member, at most 100.
        """

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry.

        Args:
            session_token: Live Session token from `join`.
            address: Agent name or qualified Address in this Team.
        """

    def events(self, session_token: str) -> AsyncIterator[dict[str, Any]]:
        """Yield work-hint events until the Session ends.

        `work_available` is a hint to call `lease`. Unknown types are
        ignored by the Client. Correctness does not depend on this stream.

        Args:
            session_token: Live Session token from `join`.
        """

    async def close(self) -> None:
        """Release transport resources. Does not disconnect the Session."""
