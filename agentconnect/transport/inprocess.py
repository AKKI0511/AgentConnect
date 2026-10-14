"""In-process Runtime transport.

Calls operations on a Team-like object by method name. This module does
not import `agentconnect.team`, so `agent/` can use it without crossing
the import boundary. Everyday Agent code uses `BaseAgent.join` with a
started Team rather than constructing this class.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Mapping

from agentconnect.transport.runtime import wrap_runtime_error


class InProcessTransport:
    """Runtime operations as direct calls on an embedded Team.

    Session transport. Token-taking methods match `Team` by name.
    """

    def __init__(self, runtime: Any) -> None:
        """Call operations on `runtime` by method name. Does not import team.

        Args:
            runtime: A started `Team`.

        Raises:
            TypeError: `runtime` is missing or is a string URL.
        """
        if runtime is None or isinstance(runtime, (str, bytes)):
            raise TypeError("in-process transport needs a started Team")
        self._runtime = runtime

    async def join_challenge(self) -> dict[str, Any]:
        """Return a one-time join challenge from the embedded Team.

        Raises:
            TransportError: The Runtime rejected the call.
        """
        try:
            return await self._runtime.join_challenge()
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def join(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Create or reconnect a Membership and open a Session.

        Args:
            request: Join body (`name`, `agent_did`, `profile`, …).

        Raises:
            TransportError: The Runtime rejected the call.
        """
        try:
            return await self._runtime.join(request=request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def disconnect(self, session_token: str) -> None:
        """Close this Session. Membership is retained.

        Args:
            session_token: Live Session token from `join`.

        Raises:
            TransportError: The Session is missing or expired.
        """
        try:
            await self._runtime.disconnect(session_token)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Prove the Client still holds its Session and extend expiry.

        Args:
            session_token: Live Session token from `join`.

        Raises:
            TransportError: The Session is missing or expired.
        """
        try:
            return await self._runtime.heartbeat(session_token)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept one request or event for one recipient.

        Session transport. Agent code uses `BaseAgent.ask`.

        Args:
            session_token: Live Session token from `join`.
            request: Send body (`id`, `recipient`, `kind`, `content`, …).

        Raises:
            TransportError: The Runtime rejected the send.
        """
        try:
            return await self._runtime.send(session_token, request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """Pull available work from this Membership's Mailbox.

        Args:
            session_token: Live Session token from `join`.
            max_items: How many Deliveries to take, 1 to 100.

        Raises:
            TransportError: The Runtime rejected the lease.
        """
        try:
            return await self._runtime.lease(session_token, max_items)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def renew(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Extend one active Delivery lease.

        Args:
            session_token: Live Session token from `join`.
            lease_id: `lease_id` from a Delivery this Session holds.

        Raises:
            TransportError: The lease is missing or expired.
        """
        try:
            return await self._runtime.renew(session_token, lease_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Finish a Delivery without a response Message.

        Args:
            session_token: Live Session token from `join`.
            lease_id: `lease_id` from a Delivery this Session holds.

        Raises:
            TransportError: The Runtime rejected the complete.
        """
        try:
            return await self._runtime.complete(session_token, lease_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a reply-expected Delivery with a response or error.

        Args:
            session_token: Live Session token from `join`.
            request: Reply body (`id`, `lease_id`, `outcome`, …).

        Raises:
            TransportError: The Runtime rejected the reply.
        """
        try:
            return await self._runtime.reply(session_token, request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return a Ticket this Membership owns.

        Args:
            session_token: Live Session token from `join`.
            ticket_id: Ticket id from a request this Membership sent.

        Raises:
            TransportError: The Ticket is missing or not owned by this
                Membership.
        """
        try:
            return await self._runtime.get_result(session_token, ticket_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

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

        Raises:
            TransportError: The Thread is missing or this Membership is
                not a participant.
        """
        try:
            return await self._runtime.get_history(
                session_token, thread_id, before=before, limit=limit
            )
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

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

        Raises:
            TransportError: The query is invalid or ranking cannot run.
        """
        try:
            return await self._runtime.find(session_token, query, limit=limit)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry.

        Args:
            session_token: Live Session token from `join`.
            address: Agent name or qualified Address in this Team.

        Raises:
            TransportError: The Address is invalid or no Membership matches.
        """
        try:
            return await self._runtime.get_profile(session_token, address)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def events(self, session_token: str) -> AsyncIterator[dict[str, Any]]:
        """Yield work hints when the Mailbox has leaseable items.

        Args:
            session_token: Live Session token from `join`.
        """
        wait = getattr(self._runtime, "_wait_for_work", None)
        if wait is None:
            return
        while True:
            try:
                found = await wait(session_token, timeout=1.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = wrap_runtime_error(exc)
                if error.code == "unauthorized":
                    return
                raise error from exc
            if found:
                yield {"type": "work_available", "data": {}}
                await asyncio.sleep(0.05)

    async def close(self) -> None:
        """No-op. The embedded Team is owned by the caller. Does not disconnect the Session."""
        return
