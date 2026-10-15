"""Direct connectivity to an embedded Team."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Protocol, runtime_checkable

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

from agentconnect.transport.runtime import RuntimeOperations, wrap_runtime_error


@runtime_checkable
class _WorkHints(Protocol):
    async def _wait_for_work(
        self, session_token: SessionToken, timeout: float = 30.0
    ) -> bool: ...


class InProcessTransport:
    """Use the RuntimeTransport operations against a started Team in this process.

    The caller owns the Team. Runtime failures become `TransportError`;
    async cancellation propagates. The shared operation contracts are described
    on `RuntimeTransport`. Ordinary agents select this transport with `BaseAgent.join`.
    """

    def __init__(self, runtime: RuntimeOperations) -> None:
        """Use an existing started Team; construction does not start it.

        Raises:
            TypeError: The supplied Runtime is absent or a URL.
        """
        if runtime is None or isinstance(runtime, (str, bytes)):
            raise TypeError("in-process transport needs a started Team")
        self._runtime = runtime

    async def join_challenge(self) -> JoinChallenge:
        """Obtain a fresh challenge from the embedded Team."""
        try:
            return await self._runtime.join_challenge()
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def join(self, request: JoinRequest) -> JoinResult:
        """Open a Session on the embedded Team using the public JoinRequest body."""
        try:
            return await self._runtime.join(request=request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def disconnect(self, session_token: SessionToken) -> None:
        """End the Session on the embedded Team; its Membership and accepted work remain."""
        try:
            await self._runtime.disconnect(session_token)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def heartbeat(self, session_token: SessionToken) -> HeartbeatResult:
        """Renew Session expiry on the embedded Team, leaving Delivery leases unchanged."""
        try:
            return await self._runtime.heartbeat(session_token)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def send(
        self, session_token: SessionToken, request: SendRequest
    ) -> SendResult:
        """Submit work directly to the Team; an ended wait does not cancel accepted work."""
        try:
            return await self._runtime.send(session_token, request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def lease(
        self, session_token: SessionToken, max_items: int = 1
    ) -> LeaseResult:
        """Lease available attempts from the embedded Team within Session capacity."""
        try:
            return await self._runtime.lease(session_token, max_items)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def renew(self, session_token: SessionToken, lease_id: Uuid) -> RenewResult:
        """Renew an active attempt owned by the Session."""
        try:
            return await self._runtime.renew(session_token, lease_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def complete(
        self, session_token: SessionToken, lease_id: Uuid
    ) -> CompleteResult:
        """Complete an event or decline a request under an active Session-owned lease."""
        try:
            return await self._runtime.complete(session_token, lease_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def reply(
        self, session_token: SessionToken, request: ReplyRequest
    ) -> ReplyResult:
        """Submit a successful or failed reply under an active Session-owned request lease."""
        try:
            return await self._runtime.reply(session_token, request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_result(self, session_token: SessionToken, ticket_id: Uuid) -> Ticket:
        """Read a retained Ticket owned by this Membership from the embedded Team."""
        try:
            return await self._runtime.get_result(session_token, ticket_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_history(
        self,
        session_token: SessionToken,
        thread_id: Uuid,
        *,
        before: Uuid | None = None,
        limit: int = 50,
    ) -> HistoryResult:
        """Read a retained history page for a Thread this Membership participates in."""
        try:
            return await self._runtime.get_history(
                session_token, thread_id, before=before, limit=limit
            )
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def find(
        self,
        session_token: SessionToken,
        query: str,
        *,
        limit: int | None = None,
    ) -> FindResult:
        """Read ranked discovery candidates from the embedded Team."""
        try:
            return await self._runtime.find(session_token, query, limit=limit)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_profile(
        self, session_token: SessionToken, address: Address
    ) -> DirectoryEntry:
        """Read a full Directory entry for a same-Team Address."""
        try:
            return await self._runtime.get_profile(session_token, address)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def events(self, session_token: SessionToken) -> AsyncIterator[RuntimeEvent]:
        """Yield work hints while the embedded Team makes attempts available.

        Ends when the Session is unauthorized. A Runtime without a work-hint stream
        can yield nothing; callers still lease work. Cancellation propagates.
        """
        if not isinstance(self._runtime, _WorkHints):
            return
        while True:
            try:
                found = await self._runtime._wait_for_work(session_token, timeout=1.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = wrap_runtime_error(exc)
                if error.code == "unauthorized":
                    return
                raise error from exc
            if found:
                yield RuntimeEvent(type="work_available", data={})
                await asyncio.sleep(0.05)

    async def close(self) -> None:
        """Release no resources; the application owns and stops the embedded Team."""
        return
