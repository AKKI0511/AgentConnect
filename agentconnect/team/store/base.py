"""Persistence used only by the Team Runtime.

A Store holds Memberships, Sessions, Mailboxes, Messages, Tickets, and
Thread history. Agents never talk to it. Memory is the default for a
process-local Team. Redis keeps that state across a Runtime restart.

Contention uses two primitives: insert-if-absent and compare-and-set
against a document version. Mailbox ready sets and expiry are
time-ordered indexes so enqueue and sweep do not walk every stored id.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class StoreRecord:
    """One stored document plus the version compare-and-set expects.

    ``version`` starts at ``1`` on insert. A successful compare-and-set
    stores ``version + 1``.
    """

    value: Any
    version: int


class Store(ABC):
    """Key-value document store plus sets and a time-ordered index.

    Custom backends implement this for a Team. Ordinary Agent code never
    constructs a Store.

        record = await store.get_record("ticket:abc")
        if record is not None:
            ok = await store.compare_and_set(
                "ticket:abc", record.version, updated
            )
    """

    persistence: str

    @abstractmethod
    async def open(self) -> None:
        """Connect and prepare the backend."""

    @abstractmethod
    async def close(self) -> None:
        """Release backend resources."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return the JSON-compatible value at ``key``, or None."""

    @abstractmethod
    async def get_record(self, key: str) -> StoreRecord | None:
        """Return value and version at ``key``, or None."""

    @abstractmethod
    async def put(self, key: str, value: Any) -> None:
        """Unconditionally write a JSON-compatible value at ``key``."""

    @abstractmethod
    async def insert(self, key: str, value: Any) -> bool:
        """Write ``value`` only if ``key`` is absent. True when inserted."""

    @abstractmethod
    async def compare_and_set(self, key: str, version: int, value: Any) -> bool:
        """Replace ``key`` when its stored version equals ``version``.

        The stored version becomes ``version + 1``. False if the key is
        missing or the version does not match.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove ``key`` if it exists, including set and index data."""

    @abstractmethod
    async def set_add(self, key: str, member: str) -> None:
        """Add ``member`` to the set at ``key``."""

    @abstractmethod
    async def set_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the set at ``key``."""

    @abstractmethod
    async def set_members(self, key: str) -> list[str]:
        """Return the members of the set at ``key``."""

    @abstractmethod
    async def index_add(self, key: str, score: float, member: str) -> None:
        """Add or update ``member`` in the sorted index at ``key``."""

    @abstractmethod
    async def index_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the sorted index at ``key``."""

    @abstractmethod
    async def index_range(
        self,
        key: str,
        *,
        max_score: float,
        min_score: float = float("-inf"),
        limit: Optional[int] = None,
    ) -> list[str]:
        """Return members with scores in ``[min_score, max_score]``, lowest first."""

    @abstractmethod
    async def index_card(self, key: str) -> int:
        """Return the number of members in the sorted index at ``key``."""

    @abstractmethod
    async def index_add_if_card_below(
        self, key: str, score: float, member: str, max_card: int
    ) -> bool:
        """Add ``member`` when the index has fewer than ``max_card`` members.

        Updating an existing member's score always succeeds and does not
        change cardinality. True when the member is in the index afterwards.
        """

    @abstractmethod
    async def increment_if_below(
        self,
        key: str,
        limit: int,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> bool:
        """Atomically increment an integer document when it is below ``limit``.

        Missing keys start at ``0``. True when the increment happened.
        ``ttl_seconds`` is a hint for durable backends; memory ignores it.
        """

    @abstractmethod
    async def decrement_floor(
        self,
        key: str,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> int:
        """Decrement an integer document, not below ``0``. Return the new value."""

    async def exists(self, key: str) -> bool:
        """Return True when ``key`` has a value."""
        return await self.get(key) is not None

    async def ping(self) -> None:
        """Confirm the backend is reachable. Memory stores no-op."""

    async def clear(self) -> None:
        """Delete every key owned by this store. Used by tests."""
