"""In-process Store. State survives Client disconnects, not process exit."""

from __future__ import annotations

import asyncio
from typing import Any

from agentconnect.team.store.base import Store


class MemoryStore(Store):
    """Volatile document store backed by dicts in this process."""

    persistence = "volatile"

    def __init__(self) -> None:
        """Create an empty in-process store."""
        self._lock = asyncio.Lock()
        self._docs: dict[str, Any] = {}
        self._sets: dict[str, set[str]] = {}

    async def open(self) -> None:
        """No-op. The store is ready after construction."""
        return None

    async def close(self) -> None:
        """No-op. Memory is not wiped on close."""
        return None

    async def get(self, key: str) -> Any | None:
        """Return a copy of the value at ``key``, or None."""
        async with self._lock:
            value = self._docs.get(key)
            if value is None:
                return None
            return _clone(value)

    async def put(self, key: str, value: Any) -> None:
        """Write a copied value at ``key``."""
        async with self._lock:
            self._docs[key] = _clone(value)

    async def delete(self, key: str) -> None:
        """Remove ``key`` from documents and sets."""
        async with self._lock:
            self._docs.pop(key, None)
            self._sets.pop(key, None)

    async def set_add(self, key: str, member: str) -> None:
        """Add ``member`` to the set at ``key``."""
        async with self._lock:
            self._sets.setdefault(key, set()).add(member)

    async def set_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the set at ``key``."""
        async with self._lock:
            members = self._sets.get(key)
            if members is None:
                return
            members.discard(member)
            if not members:
                self._sets.pop(key, None)

    async def set_members(self, key: str) -> list[str]:
        """Return the sorted members of the set at ``key``."""
        async with self._lock:
            members = self._sets.get(key)
            if not members:
                return []
            return sorted(members)

    async def ping(self) -> None:
        """No-op. Memory is always reachable."""
        return None

    async def clear(self) -> None:
        """Delete every document and set in this process store."""
        async with self._lock:
            self._docs.clear()
            self._sets.clear()


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
