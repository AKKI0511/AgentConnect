"""In-process Store. State survives Client disconnects, not process exit."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from agentconnect.team.store.base import Store, StoreRecord


class MemoryStore(Store):
    """Volatile document store backed by dicts in this process.

    ``insert`` and ``compare_and_set`` are atomic with respect to other
    MemoryStore operations. Mailbox index updates use the same lock.
    """

    persistence = "volatile"

    def __init__(self) -> None:
        """Create an empty in-process store."""
        self._lock = asyncio.Lock()
        self._docs: dict[str, tuple[Any, int]] = {}
        self._sets: dict[str, set[str]] = {}
        self._indexes: dict[str, dict[str, float]] = {}

    async def open(self) -> None:
        """No-op. The store is ready after construction."""
        return None

    async def close(self) -> None:
        """No-op. Memory is not wiped on close."""
        return None

    async def get(self, key: str) -> Any | None:
        """Return a copy of the value at ``key``, or None."""
        async with self._lock:
            record = self._docs.get(key)
            if record is None:
                return None
            return _clone(record[0])

    async def get_record(self, key: str) -> StoreRecord | None:
        """Return a copied value and its version, or None."""
        async with self._lock:
            record = self._docs.get(key)
            if record is None:
                return None
            return StoreRecord(value=_clone(record[0]), version=record[1])

    async def put(self, key: str, value: Any) -> None:
        """Write a copied value at ``key``, bumping the version."""
        async with self._lock:
            previous = self._docs.get(key)
            version = 1 if previous is None else previous[1] + 1
            self._docs[key] = (_clone(value), version)

    async def insert(self, key: str, value: Any) -> bool:
        """Write ``value`` only if ``key`` is absent."""
        async with self._lock:
            if key in self._docs:
                return False
            self._docs[key] = (_clone(value), 1)
            return True

    async def compare_and_set(self, key: str, version: int, value: Any) -> bool:
        """Replace ``key`` when the stored version matches."""
        async with self._lock:
            record = self._docs.get(key)
            if record is None or record[1] != version:
                return False
            self._docs[key] = (_clone(value), version + 1)
            return True

    async def delete(self, key: str) -> None:
        """Remove ``key`` from documents, sets, and indexes."""
        async with self._lock:
            self._docs.pop(key, None)
            self._sets.pop(key, None)
            self._indexes.pop(key, None)

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

    async def index_add(self, key: str, score: float, member: str) -> None:
        """Add or update ``member`` in the sorted index at ``key``."""
        async with self._lock:
            self._indexes.setdefault(key, {})[member] = float(score)

    async def index_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the sorted index at ``key``."""
        async with self._lock:
            index = self._indexes.get(key)
            if index is None:
                return
            index.pop(member, None)
            if not index:
                self._indexes.pop(key, None)

    async def index_range(
        self,
        key: str,
        *,
        max_score: float,
        min_score: float = float("-inf"),
        limit: Optional[int] = None,
    ) -> list[str]:
        """Return members with scores in ``[min_score, max_score]``, lowest first."""
        async with self._lock:
            index = self._indexes.get(key) or {}
            ordered = sorted(
                (
                    (score, member)
                    for member, score in index.items()
                    if min_score <= score <= max_score
                )
            )
            members = [member for _score, member in ordered]
            if limit is None:
                return members
            return members[: max(0, int(limit))]

    async def index_card(self, key: str) -> int:
        """Return the number of members in the sorted index at ``key``."""
        async with self._lock:
            index = self._indexes.get(key)
            return 0 if not index else len(index)

    async def index_add_if_card_below(
        self, key: str, score: float, member: str, max_card: int
    ) -> bool:
        """Add ``member`` when the index has fewer than ``max_card`` members."""
        async with self._lock:
            index = self._indexes.setdefault(key, {})
            if member in index:
                index[member] = float(score)
                return True
            if len(index) >= max_card:
                return False
            index[member] = float(score)
            return True

    async def increment_if_below(
        self,
        key: str,
        limit: int,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> bool:
        """Increment an integer document when it is below ``limit``."""
        del ttl_seconds
        async with self._lock:
            record = self._docs.get(key)
            current = 0 if record is None else int(record[0] or 0)
            if current >= limit:
                return False
            version = 1 if record is None else record[1] + 1
            self._docs[key] = (current + 1, version)
            return True

    async def decrement_floor(
        self,
        key: str,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> int:
        """Decrement an integer document, not below ``0``."""
        del ttl_seconds
        async with self._lock:
            record = self._docs.get(key)
            current = 0 if record is None else int(record[0] or 0)
            nxt = max(0, current - 1)
            if record is None and nxt == 0:
                return 0
            version = 1 if record is None else record[1] + 1
            self._docs[key] = (nxt, version)
            return nxt

    async def ping(self) -> None:
        """No-op. Memory is always reachable."""
        return None

    async def clear(self) -> None:
        """Delete every document, set, and index in this process store."""
        async with self._lock:
            self._docs.clear()
            self._sets.clear()
            self._indexes.clear()


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
