"""In-process Runtime transport.

Calls operations on a Team-like object by method name. This module does
not import ``agentconnect.team``, so ``agent/`` can use it without
crossing the import boundary.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Mapping

from agentconnect.transport.runtime import wrap_runtime_error


class InProcessTransport:
    """Runtime operations as direct calls on an embedded Team."""

    def __init__(self, runtime: Any) -> None:
        """Call operations on ``runtime`` by method name. Does not import team."""
        if runtime is None or isinstance(runtime, (str, bytes)):
            raise TypeError("in-process transport needs a started Team")
        self._runtime = runtime

    async def join_challenge(self) -> dict[str, Any]:
        """Return a one-time join challenge from the embedded Team."""
        try:
            return await self._runtime.join_challenge()
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def join(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Create or reconnect a Membership and open a Session."""
        try:
            return await self._runtime.join(request=request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def disconnect(self, session_token: str) -> None:
        """Close this Session. Membership is retained."""
        try:
            await self._runtime.disconnect(session_token)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Refresh Session expiry."""
        try:
            return await self._runtime.heartbeat(session_token)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept a Message."""
        try:
            return await self._runtime.send(session_token, request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """Lease work from this Membership's Mailbox."""
        try:
            return await self._runtime.lease(session_token, max_items)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Finish a Delivery without a response Message."""
        try:
            return await self._runtime.complete(session_token, lease_id)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a leased reply-expected Delivery."""
        try:
            return await self._runtime.reply(session_token, request)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return a Ticket this Membership owns."""
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
        """Return one page of retained Thread history."""
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
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Search this Team's Directory."""
        try:
            return await self._runtime.find(
                session_token, query, limit=limit, detail=detail
            )
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry."""
        try:
            return await self._runtime.get_profile(session_token, address)
        except Exception as exc:
            raise wrap_runtime_error(exc) from exc

    async def events(self, session_token: str) -> AsyncIterator[dict[str, Any]]:
        """Yield work hints when the Mailbox has leaseable items."""
        wait = getattr(self._runtime, "wait_for_work", None)
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
        """No-op. The embedded Team is owned by the caller."""
        return
