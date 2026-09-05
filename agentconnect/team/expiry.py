"""Time-ordered expiry indexes used by the Runtime sweep.

Each expiring record is a member of a sorted index scored by unix time.
The sweep reads :func:`due` and processes those ids. It does not walk
every stored Session, lease, Ticket, or join credential.

    await schedule(store, SESSIONS, token, session["expires_at"])
    for token in await due(store, SESSIONS, utc_now()):
        await expire_session(token)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from agentconnect.team.codec import timestamp_score
from agentconnect.team.store.base import Store

When = Union[datetime, str]

SESSIONS = "expiry:sessions"
LEASES = "expiry:leases"
OPEN_TICKETS = "expiry:tickets:open"
TERMINAL_TICKETS = "expiry:tickets:terminal"
JOIN_CHALLENGES = "expiry:join_challenges"
JOIN_TOKENS = "expiry:join_tokens"


async def schedule(store: Store, index: str, member: str, when: When) -> None:
    """Index ``member`` so the sweep pops it at ``when``."""
    await store.index_add(index, timestamp_score(when), member)


async def cancel(store: Store, index: str, member: str) -> None:
    """Drop ``member`` from an expiry index."""
    await store.index_remove(index, member)


async def due(
    store: Store,
    index: str,
    now: datetime,
    *,
    limit: Optional[int] = None,
) -> list[str]:
    """Return members whose scheduled time is at or before ``now``, earliest first."""
    return await store.index_range(index, max_score=now.timestamp(), limit=limit)
