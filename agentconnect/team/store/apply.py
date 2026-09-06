"""In-memory overlay that applies a StoreOp batch or leaves state unchanged.

MemoryStore and RedisStore both run this simulator so a transition has
the same conflict rules on either backend. The overlay copies only the
document keys the batch touches. Sets and indexes record deltas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from agentconnect.team.store.base import StoreRecord
from agentconnect.team.store.ops import (
    REASON_BUSY,
    REASON_CAS,
    REASON_EXISTS,
    REASON_LIMIT,
    ApplyResult,
    Cas,
    DecrementFloor,
    Delete,
    DeleteIfVersion,
    IncrementIfBelow,
    IndexAdd,
    IndexAddIfCardBelow,
    IndexRemove,
    Insert,
    Put,
    SetAdd,
    SetRemove,
    StoreOp,
    clone_value,
)

_MISSING = object()


@dataclass
class Overlay:
    """Mutable view of documents, sets, and indexes for one apply batch."""

    get_doc: Callable[[str], Optional[StoreRecord]]
    get_index_score: Callable[[str, str], Optional[float]]
    get_index_card: Callable[[str], int]
    docs: dict[str, Any] = field(default_factory=dict)
    wiped: set[str] = field(default_factory=set)
    set_add: dict[str, set[str]] = field(default_factory=dict)
    set_rem: dict[str, set[str]] = field(default_factory=dict)
    index_add: dict[str, dict[str, float]] = field(default_factory=dict)
    index_rem: dict[str, set[str]] = field(default_factory=dict)
    card_delta: dict[str, int] = field(default_factory=dict)
    expire: dict[str, int] = field(default_factory=dict)

    def doc(self, key: str) -> Optional[StoreRecord]:
        """Return the current document at ``key``, caching the first read."""
        if key in self.docs:
            value = self.docs[key]
            return None if value is _MISSING else value
        record = self.get_doc(key)
        self.docs[key] = _MISSING if record is None else record
        return record

    def write_doc(self, key: str, value: Any, version: int) -> None:
        """Replace the overlay document at ``key``."""
        self.docs[key] = StoreRecord(value=clone_value(value), version=int(version))

    def iter_docs(self):
        """Yield ``(key, record_or_none)`` for documents touched by the batch."""
        for key, value in self.docs.items():
            yield key, None if value is _MISSING else value

    def wipe(self, key: str) -> None:
        """Delete the document, set, and index stored at ``key``."""
        self.docs[key] = _MISSING
        self.wiped.add(key)
        self.set_add[key] = set()
        self.set_rem[key] = set()
        self.index_add[key] = {}
        self.index_rem[key] = set()
        self.card_delta[key] = 0

    def add_member(self, key: str, member: str) -> None:
        """Add ``member`` to the set at ``key``."""
        self.set_rem.setdefault(key, set()).discard(member)
        self.set_add.setdefault(key, set()).add(member)

    def drop_member(self, key: str, member: str) -> None:
        """Remove ``member`` from the set at ``key``."""
        self.set_add.setdefault(key, set()).discard(member)
        self.set_rem.setdefault(key, set()).add(member)

    def _index_has(self, key: str, member: str) -> bool:
        if key in self.wiped:
            return member in self.index_add.get(key, {})
        if member in self.index_rem.get(key, ()):
            return False
        if member in self.index_add.get(key, {}):
            return True
        return self.get_index_score(key, member) is not None

    def _index_card(self, key: str) -> int:
        if key in self.wiped:
            return len(self.index_add.get(key, {}))
        return self.get_index_card(key) + self.card_delta.get(key, 0)

    def add_index(self, key: str, member: str, score: float) -> None:
        """Add or update ``member`` in the sorted index at ``key``."""
        existed = self._index_has(key, member)
        self.index_rem.setdefault(key, set()).discard(member)
        self.index_add.setdefault(key, {})[member] = float(score)
        if not existed:
            self.card_delta[key] = self.card_delta.get(key, 0) + 1

    def drop_index(self, key: str, member: str) -> None:
        """Remove ``member`` from the sorted index at ``key``."""
        existed = self._index_has(key, member)
        self.index_add.setdefault(key, {}).pop(member, None)
        self.index_rem.setdefault(key, set()).add(member)
        if existed:
            self.card_delta[key] = self.card_delta.get(key, 0) - 1


def apply_ops(
    ops: list[StoreOp] | tuple[StoreOp, ...], overlay: Overlay
) -> ApplyResult:
    """Apply ``ops`` to ``overlay``. Stop at the first conflict."""
    for index, op in enumerate(ops):
        reason = _apply_one(op, overlay)
        if reason is not None:
            return ApplyResult(ok=False, reason=reason, op_index=index)
    return ApplyResult(ok=True)


def _apply_one(op: StoreOp, overlay: Overlay) -> Optional[str]:
    if isinstance(op, Insert):
        if overlay.doc(op.key) is not None:
            return REASON_EXISTS
        overlay.write_doc(op.key, op.value, 1)
        return None
    if isinstance(op, Cas):
        record = overlay.doc(op.key)
        if record is None or record.version != op.version:
            return REASON_CAS
        overlay.write_doc(op.key, op.value, op.version + 1)
        return None
    if isinstance(op, Put):
        record = overlay.doc(op.key)
        version = 1 if record is None else record.version + 1
        overlay.write_doc(op.key, op.value, version)
        return None
    if isinstance(op, Delete):
        overlay.wipe(op.key)
        return None
    if isinstance(op, DeleteIfVersion):
        record = overlay.doc(op.key)
        if record is None or record.version != op.version:
            return REASON_CAS
        overlay.wipe(op.key)
        return None
    if isinstance(op, SetAdd):
        overlay.add_member(op.key, op.member)
        return None
    if isinstance(op, SetRemove):
        overlay.drop_member(op.key, op.member)
        return None
    if isinstance(op, IndexAdd):
        overlay.add_index(op.key, op.member, op.score)
        return None
    if isinstance(op, IndexRemove):
        overlay.drop_index(op.key, op.member)
        return None
    if isinstance(op, IndexAddIfCardBelow):
        if overlay._index_has(op.key, op.member):
            overlay.add_index(op.key, op.member, op.score)
            return None
        if overlay._index_card(op.key) >= op.max_card:
            return REASON_BUSY
        overlay.add_index(op.key, op.member, op.score)
        return None
    if isinstance(op, IncrementIfBelow):
        record = overlay.doc(op.key)
        current = 0 if record is None else int(record.value or 0)
        if current >= op.limit:
            return REASON_LIMIT
        version = 1 if record is None else record.version + 1
        overlay.write_doc(op.key, current + 1, version)
        _note_ttl(overlay, op.key, op.ttl_seconds)
        return None
    if isinstance(op, DecrementFloor):
        record = overlay.doc(op.key)
        current = 0 if record is None else int(record.value or 0)
        nxt = max(0, current - 1)
        if record is None and nxt == 0:
            overlay.write_doc(op.key, 0, 1)
            _note_ttl(overlay, op.key, op.ttl_seconds)
            return None
        version = 1 if record is None else record.version + 1
        overlay.write_doc(op.key, nxt, version)
        _note_ttl(overlay, op.key, op.ttl_seconds)
        return None
    raise TypeError(f"unsupported store op {type(op)!r}")


def _note_ttl(overlay: Overlay, key: str, ttl_seconds: Optional[float]) -> None:
    if ttl_seconds is None:
        return
    overlay.expire[key] = max(1, int(ttl_seconds))


def watch_keys(
    ops: list[StoreOp] | tuple[StoreOp, ...],
) -> tuple[set[str], set[str], set[str]]:
    """Return document, set, and index keys referenced by ``ops``."""
    docs: set[str] = set()
    sets: set[str] = set()
    indexes: set[str] = set()
    for op in ops:
        if isinstance(op, (Insert, Cas, Put, IncrementIfBelow, DecrementFloor)):
            docs.add(op.key)
        elif isinstance(op, (Delete, DeleteIfVersion)):
            docs.add(op.key)
            sets.add(op.key)
            indexes.add(op.key)
        elif isinstance(op, (SetAdd, SetRemove)):
            sets.add(op.key)
        elif isinstance(op, (IndexAdd, IndexRemove, IndexAddIfCardBelow)):
            indexes.add(op.key)
    return docs, sets, indexes
