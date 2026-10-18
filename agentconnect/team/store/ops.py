"""Atomic batch operations for custom `Store.apply` implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, SupportsInt, SupportsIndex, Union

REASON_EXISTS = "exists"
REASON_CAS = "cas"
REASON_BUSY = "busy"
REASON_LIMIT = "limit"


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of an atomic batch."""

    ok: bool
    """True after every operation commits; False leaves the store unchanged."""
    reason: Optional[str] = None
    """None on success. Conflicts are `exists` for an existing insert key,
    `cas` for a missing or mismatched version, `busy` for an index
    cardinality cap, and `limit` for an increment cap.
    """
    op_index: Optional[int] = None
    """Zero-based conflicting operation index.
    None when unknown or successful.
    """


@dataclass(frozen=True)
class Insert:
    """Write `value` only if `key` is absent. Fails the batch with `exists`."""

    key: str
    """Document key."""
    value: object
    """JSON-compatible document."""


@dataclass(frozen=True)
class Cas:
    """Replace `key` when its stored version equals `version`.

    Store a copy at `version + 1`. A missing key or mismatched version
    fails the batch with `cas`.
    """

    key: str
    """Document key."""
    version: int
    """Expected current version."""
    value: object
    """JSON-compatible document to store."""


@dataclass(frozen=True)
class Put:
    """Unconditionally write `value`, bumping the stored version."""

    key: str
    """Document key."""
    value: object
    """JSON-compatible document."""


@dataclass(frozen=True)
class Delete:
    """Remove the document, set, and index stored at `key`."""

    key: str
    """Document, set, or index key."""


@dataclass(frozen=True)
class DeleteIfVersion:
    """Delete `key` only when its stored version equals `version`.

    A missing key or mismatched version fails the batch with `cas`.
    A match removes the document, set, and index at that key.
    """

    key: str
    """Document key."""
    version: int
    """Expected current version."""


@dataclass(frozen=True)
class SetAdd:
    """Add `member` to the set at `key`."""

    key: str
    """Set key."""
    member: str
    """Value to add."""


@dataclass(frozen=True)
class SetRemove:
    """Remove `member` from the set at `key`."""

    key: str
    """Set key."""
    member: str
    """Value to remove."""


@dataclass(frozen=True)
class IndexAdd:
    """Add or update `member` in the sorted index at `key`."""

    key: str
    """Index key."""
    score: float
    """Sort score."""
    member: str
    """Indexed member."""


@dataclass(frozen=True)
class IndexRemove:
    """Remove `member` from the sorted index at `key`."""

    key: str
    """Index key."""
    member: str
    """Indexed member."""


@dataclass(frozen=True)
class IndexAddIfCardBelow:
    """Add `member` when the index has fewer than `max_card` members.

    Updating an existing member's score always succeeds. A new member
    past the cap fails the batch with `busy`.
    """

    key: str
    """Index key."""
    score: float
    """Sort score."""
    member: str
    """Indexed member."""
    max_card: int
    """Maximum distinct members allowed."""


@dataclass(frozen=True)
class IncrementIfBelow:
    """Atomically increment an integer document when it is below `limit`.

    A missing document starts at zero. Hitting the cap fails the batch
    with `limit`. A write advances its version. TTL follows
    `Store.increment_if_below`; memory ignores the hint.
    """

    key: str
    """Integer document key."""
    limit: int
    """Exclusive upper bound for the value before increment."""
    ttl_seconds: Optional[float] = None
    """Lifetime hint for durable backends."""


@dataclass(frozen=True)
class DecrementFloor:
    """Decrement an integer document, not below `0`.

    Always writes, creating zero at version 1 if the key is absent, or
    advancing the existing version. TTL follows `Store.increment_if_below`;
    memory ignores the hint. This operation cannot conflict on its own.
    """

    key: str
    """Integer document key."""
    ttl_seconds: Optional[float] = None
    """Lifetime hint for durable backends."""


StoreOp = Union[
    Insert,
    Cas,
    Put,
    Delete,
    DeleteIfVersion,
    SetAdd,
    SetRemove,
    IndexAdd,
    IndexRemove,
    IndexAddIfCardBelow,
    IncrementIfBelow,
    DecrementFloor,
]


def _clone_value(value: object) -> object:
    """Return a deep copy of a JSON-compatible value.

    Args:
        value: Mapping, list, or scalar.

    Returns:
        A new nested structure; scalars are returned unchanged.
    """
    if isinstance(value, dict):
        return {key: _clone_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_value(item) for item in value]
    return value


def _integer_document(value: object) -> int:
    # Integer counters retain int() semantics at the generic document boundary.
    if isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)):
        return int(value)
    raise TypeError("integer document must support int conversion")
