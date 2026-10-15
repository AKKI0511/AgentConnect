"""Connection contracts for custom Runtime transports."""

from __future__ import annotations

from typing import AsyncIterator, Mapping, Optional, Protocol

from pydantic import TypeAdapter

from agentconnect.core.base import JsonObject, JsonValue
from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.operations import (
    CompleteResult,
    HeartbeatResult,
    HistoryResult,
    JoinChallenge,
    JoinRequest,
    JoinResult,
    LeaseResult,
    RenewResult,
    ReplyRequest,
    ReplyResult,
    RuntimeEvent,
    SendRequest,
    SendResult,
)
from agentconnect.core.ticket import Ticket
from agentconnect.core.primitives import Address, SessionToken, Uuid

from agentconnect.core.spec import SPEC_VERSION

_ERROR_DETAILS: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)

__all__ = ["SPEC_VERSION", "RuntimeOperations", "RuntimeTransport", "TransportError"]


class TransportError(Exception):
    """A rejected Runtime operation or a failure to reach the Runtime.

    Branch on `code`, rather than the explanation. An `unavailable` error after
    sending does not establish whether the work was accepted.

    Attributes:
        details: Extra failure data safe for the caller.
        retryable: Whether an identical later call may succeed; None means unknown.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[JsonObject] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        """Record the failure and any Runtime-supplied details or retry advice."""
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable

    @classmethod
    def from_error_object(cls, body: Mapping[str, JsonValue]) -> "TransportError":
        """Convert Runtime error data into an exception.

        Missing code or message becomes an `internal` failure with a generic explanation.
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
        details: object = getattr(exc, "details", None)
        retryable: object = getattr(exc, "retryable", None)
        try:
            parsed_details = (
                _ERROR_DETAILS.validate_python(details) if details is not None else None
            )
        except ValueError:
            return TransportError("internal", "Runtime returned invalid error details")
        return TransportError(
            code,
            message,
            details=parsed_details,
            retryable=retryable if isinstance(retryable, bool) else None,
        )
    return TransportError("internal", str(exc) or "Runtime operation failed")


class RuntimeOperations(Protocol):
    """Shared Team operations used by transports and advanced clients.

    Requests and results use core models. Team's public parsing entry points
    also accept raw mappings; normalize external JSON before typed workflows.
    """

    async def join(self, *, request: JoinRequest) -> JoinResult:
        """Create or reconnect a Membership and return its new Session credentials.

        Accept the public JoinRequest body and return JoinResult data. Authenticated
        admission requires a Team join token and a fresh proof for the retained Agent
        DID. Reusing an Instance id replaces that Instance's old Session.
        """

    async def join_challenge(self) -> JoinChallenge:
        """Return JoinChallenge data for a fresh, short-lived proof of Agent key control."""

    async def disconnect(self, session_token: SessionToken) -> None:
        """End the Session, releasing its active Delivery attempts for recovery.

        Retain the Membership and accepted work. Further calls under this token fail
        with `unauthorized`.
        """

    async def heartbeat(self, session_token: SessionToken) -> HeartbeatResult:
        """Extend Session expiry and return HeartbeatResult data; Delivery leases are unchanged."""

    async def send(
        self, session_token: SessionToken, request: SendRequest
    ) -> SendResult:
        """Accept a public SendRequest and return SendResult data.

        Use the same Message id and body for retries after uncertain acceptance.
        Events return an acceptance acknowledgement; requests return a saved Ticket.
        `collect="wait"` may return open work when the Runtime hold ends. Cancellation
        or a lost response does not establish whether the Runtime accepted the send.
        """

    async def lease(
        self, session_token: SessionToken, max_items: int = 1
    ) -> LeaseResult:
        """Return LeaseResult data for available work within the Session's capacity.

        `max_items` must be from 1 to 100. Fewer attempts, including none, may be
        returned. Only this Session may renew, complete or reply under these leases.
        """

    async def renew(self, session_token: SessionToken, lease_id: Uuid) -> RenewResult:
        """Extend a live lease owned by this Session and return RenewResult data; work deadlines are unchanged."""

    async def complete(
        self, session_token: SessionToken, lease_id: Uuid
    ) -> CompleteResult:
        """Finish a live lease owned by this Session and return CompleteResult data.

        Completing an event ends it; completing a request declines its Ticket without
        a reply or failure.
        """

    async def reply(
        self, session_token: SessionToken, request: ReplyRequest
    ) -> ReplyResult:
        """Finish a request Delivery with a public ReplyRequest and return ReplyResult data.

        Use an active lease owned by this Session. Keep the reply id and outcome
        unchanged for replay. Successful JSON-null content is a valid reply.
        """

    async def get_result(self, session_token: SessionToken, ticket_id: Uuid) -> Ticket:
        """Return saved wire Ticket data owned by the calling Membership.

        Collection is repeatable and does not consume or cancel work. Missing or
        inaccessible Tickets fail with `not_found`.
        """

    async def get_history(
        self,
        session_token: SessionToken,
        thread_id: Uuid,
        *,
        before: Uuid | None = None,
        limit: int = 50,
    ) -> HistoryResult:
        """Return HistoryResult data for a Thread the caller participates in.

        The newest page comes first; Messages within it are in ascending `seq` order.
        Use `next_before` as the next `before` until `has_more` is false.

        Args:
            limit: Page size from 1 to 200.
        """

    async def find(
        self,
        session_token: SessionToken,
        query: str,
        *,
        limit: int | None = None,
    ) -> FindResult:
        """Return ranked FindResult candidates from this Team's Directory.

        Args:
            limit: Maximum matches from 1 to 100. Omit for every other member,
                capped at 100.
        """

    async def get_profile(
        self, session_token: SessionToken, address: Address
    ) -> DirectoryEntry:
        """Return DirectoryEntry data for a local name or same-Team qualified Address."""


class RuntimeTransport(RuntimeOperations, Protocol):
    """The supported connection contract for advanced clients and transport authors.

    Methods accept canonical request models and return canonical Runtime results.
    `RuntimeOperations` defines the shared operation contracts. Bind token-taking
    calls to the Session issued by join, preserving caller authority and result
    shapes. Report rejected operations through `TransportError` with the Runtime's
    code, message, details and retry advice. Connection failures must not be
    reported as proof that work was rejected.

    Use finite operation timeouts that cover the negotiated wait hold. Preserve
    caller cancellation; cancelling a wait does not cancel accepted work. Events
    are optional delivery hints. `close` releases transport resources, while
    `disconnect` ends a Session. The application owns the Team lifecycle.
    """

    def events(self, session_token: SessionToken) -> AsyncIterator[RuntimeEvent]:
        """Yield event objects with `type` and `data` until the stream ends.

        `work_available` is a hint to lease; clients ignore unknown types. Delivery
        must still work when this stream is absent or interrupted. Propagate caller
        cancellation and release stream resources when iteration ends.
        """

    async def close(self) -> None:
        """Release resources owned by the transport; disconnect the Session separately."""
