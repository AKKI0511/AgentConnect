"""Atomic store operations used by Runtime transitions.

A transition builds a list of these operations and passes them to
:meth:`~agentconnect.team.store.base.Store.apply`. The backend applies
every operation or none of them. Ordinary Agent code never constructs
these values.

    from agentconnect.team.store import Insert, Store

    result = await store.apply(
        [
            Insert("msg:abc", message),
            Insert("ticket:abc", ticket),
        ]
    )
    if not result.ok and result.reason == "exists":
        ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

REASON_EXISTS = "exists"
REASON_CAS = "cas"
REASON_BUSY = "busy"
REASON_LIMIT = "limit"


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of :meth:`~agentconnect.team.store.base.Store.apply`.

    ``ok`` means every operation committed. When ``ok`` is False, the
    store is unchanged. ``reason`` is ``exists`` (insert hit a live
    key), ``cas`` (version mismatch or missing CAS target), ``busy``
    (index cardinality cap), or ``limit`` (increment cap).
    """

    ok: bool
    reason: Optional[str] = None
    op_index: Optional[int] = None


@dataclass(frozen=True)
class Insert:
    """Write ``value`` only if ``key`` is absent. Fails the batch with ``exists``."""

    key: str
    value: Any


@dataclass(frozen=True)
class Cas:
    """Replace ``key`` when its stored version equals ``version``."""

    key: str
    version: int
    value: Any


@dataclass(frozen=True)
class Put:
    """Unconditionally write ``value``, bumping the stored version."""

    key: str
    value: Any


@dataclass(frozen=True)
class Delete:
    """Remove the document, set, and index stored at ``key``."""

    key: str


@dataclass(frozen=True)
class DeleteIfVersion:
    """Delete ``key`` only when its stored version equals ``version``."""

    key: str
    version: int


@dataclass(frozen=True)
class SetAdd:
    """Add ``member`` to the set at ``key``."""

    key: str
    member: str


@dataclass(frozen=True)
class SetRemove:
    """Remove ``member`` from the set at ``key``."""

    key: str
    member: str


@dataclass(frozen=True)
class IndexAdd:
    """Add or update ``member`` in the sorted index at ``key``."""

    key: str
    score: float
    member: str


@dataclass(frozen=True)
class IndexRemove:
    """Remove ``member`` from the sorted index at ``key``."""

    key: str
    member: str


@dataclass(frozen=True)
class IndexAddIfCardBelow:
    """Add ``member`` when the index has fewer than ``max_card`` members.

    Updating an existing member's score always succeeds. A new member
    past the cap fails the batch with ``busy``.
    """

    key: str
    score: float
    member: str
    max_card: int


@dataclass(frozen=True)
class IncrementIfBelow:
    """Atomically increment an integer document when it is below ``limit``."""

    key: str
    limit: int
    ttl_seconds: Optional[float] = None


@dataclass(frozen=True)
class DecrementFloor:
    """Decrement an integer document, not below ``0``."""

    key: str
    ttl_seconds: Optional[float] = None


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


def clone_value(value: Any) -> Any:
    """Return a deep copy of a JSON-compatible value."""
    if isinstance(value, dict):
        return {key: clone_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone_value(item) for item in value]
    return value
