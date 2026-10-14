"""The backend contract for Team documents, sets, and sorted indexes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from agentconnect.team.store.ops import ApplyResult, StoreOp


@dataclass(frozen=True)
class StoreRecord:
    """A stored document and its compare-and-set version."""

    value: Any
    """JSON-compatible stored document."""
    version: int
    """Starts at 1 on insertion.
    Successful compare-and-set stores `version + 1`.
    """


class Store(ABC):
    """Key-value document store plus sets and a time-ordered index.

    Implement every abstract method, then pass the backend to `Team`.
    The Team calls `open` on start and `close` on stop, including for a
    supplied backend. Close releases resources; it does not erase data.
    Reopening the same backend must preserve its state.

    Writes and reads must isolate nested JSON values from caller
    mutation. Documents, sets, and indexes have separate key spaces;
    `delete` removes all three for a key. Document versions start at 1.
    Successful writes increment the version; deleting and reinserting
    starts at 1 again. Set and index changes do not alter document versions.

    Conditional writes, capacity checks, and counters must be atomic
    with concurrent calls. `apply` also makes the whole batch atomic,
    with the ordering and conflict rules described on that method.
    Backend failures raise exceptions, rather than reporting a successful
    write or disguising an unknown outcome as a conflict.
    """

    persistence: str
    """`volatile` for process memory, or `durable` for persistent storage."""

    @abstractmethod
    async def open(self) -> None:
        """Connect and prepare the backend."""

    @abstractmethod
    async def close(self) -> None:
        """Release backend resources."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return a copy of the stored value, or None when the key is missing."""

    async def get_many(self, keys: Sequence[str]) -> list[Any | None]:
        """Return copied values in input order; missing keys are None.

        Duplicate keys keep their positions. This call does not promise a
        snapshot across all keys.
        """
        return [await self.get(key) for key in keys]

    @abstractmethod
    async def get_record(self, key: str) -> StoreRecord | None:
        """Return a copied value and its version, or None when the key is missing."""

    @abstractmethod
    async def put(self, key: str, value: Any) -> None:
        """Write a copy of `value`, starting at version 1 or incrementing it."""

    @abstractmethod
    async def insert(self, key: str, value: Any) -> bool:
        """Atomically insert a copy at version 1 if the key is absent.

        Return True if inserted, or False with the existing value unchanged.
        """

    @abstractmethod
    async def compare_and_set(self, key: str, version: int, value: Any) -> bool:
        """Atomically replace `key` when its stored version equals `version`.

        Store a copy at version `version + 1`. False if the key is
        missing or the version does not match.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove `key` if it exists, including set and index data."""

    @abstractmethod
    async def set_add(self, key: str, member: str) -> None:
        """Add `member` to the set at `key`."""

    @abstractmethod
    async def set_remove(self, key: str, member: str) -> None:
        """Remove `member` from the set at `key`."""

    @abstractmethod
    async def set_members(self, key: str) -> list[str]:
        """Return set members sorted lexicographically, without duplicates.

        A missing set returns an empty list.
        """

    async def set_is_member(self, key: str, member: str) -> bool:
        """Return whether the set contains `member`; a missing set returns False."""
        return member in await self.set_members(key)

    @abstractmethod
    async def index_add(self, key: str, score: float, member: str) -> None:
        """Add or update `member` in the sorted index at `key`."""

    @abstractmethod
    async def index_remove(self, key: str, member: str) -> None:
        """Remove `member` from the sorted index at `key`."""

    @abstractmethod
    async def index_range(
        self,
        key: str,
        *,
        max_score: float,
        min_score: float = float("-inf"),
        limit: Optional[int] = None,
    ) -> list[str]:
        """Return members in the inclusive score window, lowest score first.

        Equal scores are ordered lexicographically by member. A missing
        index returns an empty list. Use a positive `limit`; None returns
        the whole window.
        """

    @abstractmethod
    async def index_card(self, key: str) -> int:
        """Count index members; a missing index returns zero."""

    @abstractmethod
    async def index_add_if_card_below(
        self, key: str, score: float, member: str, max_card: int
    ) -> bool:
        """Add `member` when the index has fewer than `max_card` members.

        Updating an existing member's score always succeeds and does not
        change cardinality. True when the member is in the index afterwards.
        """

    @abstractmethod
    async def apply(self, ops: Sequence[StoreOp]) -> ApplyResult:
        """Apply `ops` atomically in order. Every write commits, or none do.

        A conflict returns `ok=False` and leaves the store unchanged.
        `reason` is `exists`, `cas`, `busy`, or `limit`.
        Later operations see earlier writes in the same batch, including
        their new versions. Report the first conflicting operation's
        zero-based `op_index` when known. An empty batch succeeds.
        Values are copied; changing an input after this call cannot change
        stored data. Unsupported operations raise `TypeError`.

        Examples:
            `store` is open, and `sample:note` and `sample:notes` are unused
            sample keys. Insert a note and index it together. The duplicate
            batch changes neither the note nor its index membership.

            ```python
            from agentconnect.team.store import Insert, SetAdd

            first = await store.apply(
                [
                    Insert("sample:note", {"text": "search is faster"}),
                    SetAdd("sample:notes", "release"),
                ]
            )
            second = await store.apply(
                [
                    SetAdd("sample:notes", "duplicate"),
                    Insert("sample:note", {"text": "duplicate"}),
                ]
            )
            if not second.ok:
                print(second.reason)  # exists
            saved = await store.get("sample:note")
            members = await store.set_members("sample:notes")  # ["release"]
            ```
        """

    @abstractmethod
    async def increment_if_below(
        self,
        key: str,
        limit: int,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> bool:
        """Atomically increment an integer document when it is below `limit`.

        Missing keys start at `0`. True when the increment happened.
        `ttl_seconds` is a hint for durable backends; memory ignores it.
        A successful increment advances the document version. Redis
        clears any old TTL on this write, then applies the supplied TTL
        rounded down to whole seconds, with a minimum of one second.
        A rejected increment changes neither value, version, nor TTL.
        """

    @abstractmethod
    async def decrement_floor(
        self,
        key: str,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> int:
        """Decrement an integer document, not below `0`. Return the new value.

        Missing keys read as zero. On a positive value the write advances
        the version and uses the same TTL rule as `increment_if_below`.
        A direct call at zero need not write. The batch `DecrementFloor`
        operation always writes, even at zero.
        """

    async def exists(self, key: str) -> bool:
        """Return True when `key` has a value."""
        return await self.get(key) is not None

    async def ping(self) -> None:
        """Confirm the backend is reachable. Memory stores no-op."""

    async def clear(self) -> None:
        """Delete every key owned by this store.

        Used to reset a development or test backend. Production Runtimes
        do not call this during ordinary operation.
        """
