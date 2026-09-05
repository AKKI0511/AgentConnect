"""Per-key asyncio locks for in-process Runtime coordination.

Store insert-if-absent and compare-and-set are the atomic primitives.
What remains is process-local: join Instance accounting for one
Membership, operator Session reuse, HTTP serve start, and Session
mutations that also touch in-process waiter maps.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator


class KeyedLock:
    """One ``asyncio.Lock`` per key. Unused keys are dropped after the last waiter.

    async with locks.acquire(f"member:{name}"):
        await self._join_member(...)
    """

    def __init__(self) -> None:
        """Create an empty keyed lock set."""
        self._items: dict[str, tuple[asyncio.Lock, int]] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncIterator[None]:
        """Hold the lock for ``key`` for the duration of the block."""
        async with self._guard:
            lock, count = self._items.get(key, (asyncio.Lock(), 0))
            self._items[key] = (lock, count + 1)
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
            async with self._guard:
                current = self._items.get(key)
                if current is None:
                    return
                held, count = current
                if count <= 1:
                    self._items.pop(key, None)
                else:
                    self._items[key] = (held, count - 1)
