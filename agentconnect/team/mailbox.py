"""Mailbox as a lease-based pull port.

A Mailbox is one logical queue per Agent Membership. Each item is its
own document. A time-ordered index makes enqueue constant work, depth a
cardinality, and claim a range of scores at or before now.

The four operations match a visibility-timeout queue:

- claim with a timeout
- extend that timeout
- acknowledge on complete or reply
- return on lease expiry or Session loss

    result = await enqueue(store, address, message_id, now_ts, max_depth=1000)
    ids = await ready_ids(store, address, now, limit=1)
    item = await claim(store, address, ids[0], lease_id, expires_at, now, now_ts)
    await acknowledge(store, address, message_id, lease_id)

Enqueue, claim, and acknowledge each commit their document and index
writes together. A Runtime send transition includes enqueue in a larger
apply so the item is not visible until the Message exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from agentconnect.team.codec import new_uuid, parse_timestamp, timestamp_score
import agentconnect.team.expiry as expiry_mod
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import (
    Cas,
    Delete,
    DeleteIfVersion,
    IndexAdd,
    IndexAddIfCardBelow,
    IndexRemove,
    Insert,
    Put,
    SetAdd,
    SetRemove,
    StoreOp,
)

LEASE_KEY_PREFIX = "lease:"
LEASES_SET = "leases"

EnqueueResult = Literal["ok", "busy", "duplicate"]


def mailbox_index_key(address: str) -> str:
    """Return the sorted-index key for a Membership Mailbox."""
    return f"mailbox:{address}:idx"


def mailbox_item_key(address: str, message_id: str) -> str:
    """Return the per-item document key."""
    return f"mailbox:{address}:item:{message_id}"


def lease_key(lease_id: str) -> str:
    """Return the store key for a Delivery lease record."""
    return f"{LEASE_KEY_PREFIX}{lease_id}"


def score_of(timestamp: str) -> float:
    """Return a sortable score for a Runtime timestamp."""
    return timestamp_score(timestamp)


def new_item(message_id: str, now_ts: str) -> dict[str, Any]:
    """Build a queued Mailbox item for ``message_id``."""
    return {
        "message_id": message_id,
        "enqueued_at": now_ts,
        "available_at": now_ts,
        "attempt": 0,
        "state": "queued",
        "lease_id": None,
        "lease_expires_at": None,
    }


def enqueue_ops(
    address: str,
    message_id: str,
    now_ts: str,
    *,
    max_depth: int,
) -> list[StoreOp]:
    """Return the writes that enqueue ``message_id`` if depth allows."""
    return [
        Insert(mailbox_item_key(address, message_id), new_item(message_id, now_ts)),
        IndexAddIfCardBelow(
            mailbox_index_key(address),
            score_of(now_ts),
            message_id,
            max_depth,
        ),
    ]


async def enqueue(
    store: Store,
    address: str,
    message_id: str,
    now_ts: str,
    *,
    max_depth: int,
) -> EnqueueResult:
    """Insert one Mailbox item. ``busy`` when depth would pass ``max_depth``."""
    result = await store.apply(
        enqueue_ops(address, message_id, now_ts, max_depth=max_depth)
    )
    if result.ok:
        return "ok"
    if result.reason == "exists":
        return "duplicate"
    return "busy"


async def depth(store: Store, address: str) -> int:
    """Return queued plus leased item count."""
    return await store.index_card(mailbox_index_key(address))


async def has_ready(store: Store, address: str, now: datetime) -> bool:
    """Return True when at least one Mailbox item can be claimed now."""
    ready = await ready_ids(store, address, now, limit=1)
    return bool(ready)


async def ready_ids(store: Store, address: str, now: datetime, limit: int) -> list[str]:
    """Return Message ids whose visibility timeout has elapsed, oldest first."""
    if limit <= 0:
        return []
    return await store.index_range(
        mailbox_index_key(address),
        max_score=now.timestamp(),
        limit=limit,
    )


async def claim(
    store: Store,
    address: str,
    message_id: str,
    lease_id: str,
    expires_at: str,
    now: datetime,
    now_ts: str,
) -> Optional[dict[str, Any]]:
    """Take exclusive handling of one item. None if another claimer won.

    An expired leased item is recovered: ``attempt`` rises and a new
    lease replaces the old one.
    """
    item_key = mailbox_item_key(address, message_id)
    record = await store.get_record(item_key)
    if record is None:
        await store.index_remove(mailbox_index_key(address), message_id)
        return None
    item = dict(record.value)
    if item.get("state") == "leased":
        expires = item.get("lease_expires_at")
        if expires is not None and parse_timestamp(expires) > now:
            return None
    attempt = int(item.get("attempt") or 0) + 1
    item["state"] = "leased"
    item["attempt"] = attempt
    item["lease_id"] = lease_id
    item["lease_expires_at"] = expires_at
    item["available_at"] = expires_at
    result = await store.apply(
        [
            Cas(item_key, record.version, item),
            IndexAdd(mailbox_index_key(address), score_of(expires_at), message_id),
        ]
    )
    if not result.ok:
        return None
    del now_ts
    return item


async def extend(
    store: Store,
    address: str,
    message_id: str,
    lease_id: str,
    expires_at: str,
) -> bool:
    """Refresh the visibility timeout of an active lease."""
    item_key = mailbox_item_key(address, message_id)
    record = await store.get_record(item_key)
    if record is None:
        return False
    item = dict(record.value)
    if item.get("lease_id") != lease_id or item.get("state") != "leased":
        return False
    item["lease_expires_at"] = expires_at
    item["available_at"] = expires_at
    result = await store.apply(
        [
            Cas(item_key, record.version, item),
            IndexAdd(mailbox_index_key(address), score_of(expires_at), message_id),
        ]
    )
    return result.ok


def acknowledge_ops(address: str, message_id: str, version: int) -> list[StoreOp]:
    """Return the writes that drop a Mailbox item after complete or reply."""
    return [
        DeleteIfVersion(mailbox_item_key(address, message_id), version),
        IndexRemove(mailbox_index_key(address), message_id),
    ]


async def acknowledge(
    store: Store, address: str, message_id: str, lease_id: Optional[str] = None
) -> bool:
    """Remove a claimed item after complete or reply."""
    item_key = mailbox_item_key(address, message_id)
    record = await store.get_record(item_key)
    if record is None:
        await store.index_remove(mailbox_index_key(address), message_id)
        return False
    item = record.value
    if lease_id is not None and item.get("lease_id") not in {lease_id, None}:
        return False
    result = await store.apply(acknowledge_ops(address, message_id, record.version))
    return result.ok


async def return_item(
    store: Store,
    address: str,
    message_id: str,
    lease_id: str,
    now_ts: str,
) -> bool:
    """Return a leased item to the ready set after expiry or Session loss."""
    item_key = mailbox_item_key(address, message_id)
    record = await store.get_record(item_key)
    if record is None:
        await store.index_remove(mailbox_index_key(address), message_id)
        return False
    item = dict(record.value)
    if item.get("lease_id") != lease_id:
        return False
    item["state"] = "queued"
    item["available_at"] = now_ts
    item["lease_id"] = None
    item["lease_expires_at"] = None
    result = await store.apply(
        [
            Cas(item_key, record.version, item),
            IndexAdd(mailbox_index_key(address), score_of(now_ts), message_id),
        ]
    )
    return result.ok


async def drop_item(store: Store, address: str, message_id: str) -> None:
    """Remove an item without requiring an active lease. Used on Ticket expiry."""
    await store.apply(
        [
            Delete(mailbox_item_key(address, message_id)),
            IndexRemove(mailbox_index_key(address), message_id),
        ]
    )


async def drop_mailbox(store: Store, address: str) -> None:
    """Delete every item and the index for ``address``."""
    index_key = mailbox_index_key(address)
    message_ids = await store.index_range(
        index_key, max_score=float("inf"), min_score=float("-inf")
    )
    for message_id in message_ids:
        await store.delete(mailbox_item_key(address, message_id))
    await store.delete(index_key)


def put_lease_ops(
    *,
    lease_id: str,
    message_id: str,
    address: str,
    session_token: str,
    membership_name: str,
    attempt: int,
    expires_at: str,
) -> tuple[dict[str, Any], list[StoreOp]]:
    """Return the lease record and the writes that store it."""
    record = {
        "lease_id": lease_id,
        "message_id": message_id,
        "address": address,
        "session_token": session_token,
        "membership_name": membership_name,
        "attempt": attempt,
        "expires_at": expires_at,
        "active": True,
    }
    ops: list[StoreOp] = [
        Put(lease_key(lease_id), record),
        SetAdd(LEASES_SET, lease_id),
        IndexAdd(expiry_mod.LEASES, score_of(expires_at), lease_id),
    ]
    return record, ops


async def put_lease(
    store: Store,
    *,
    lease_id: str,
    message_id: str,
    address: str,
    session_token: str,
    membership_name: str,
    attempt: int,
    expires_at: str,
) -> dict[str, Any]:
    """Store an active lease record and return it."""
    record, ops = put_lease_ops(
        lease_id=lease_id,
        message_id=message_id,
        address=address,
        session_token=session_token,
        membership_name=membership_name,
        attempt=attempt,
        expires_at=expires_at,
    )
    await store.apply(ops)
    return record


async def get_lease(store: Store, lease_id: str) -> Optional[dict[str, Any]]:
    """Load a lease record, or None if it is missing."""
    record = await store.get(lease_key(lease_id))
    if record is None:
        return None
    return record


async def deactivate_lease(store: Store, lease_id: str) -> None:
    """Mark a lease inactive and drop it from the active set."""
    record = await store.get(lease_key(lease_id))
    ops: list[StoreOp] = [
        SetRemove(LEASES_SET, lease_id),
        IndexRemove(expiry_mod.LEASES, lease_id),
    ]
    if record is not None:
        inactive = dict(record)
        inactive["active"] = False
        ops.insert(0, Put(lease_key(lease_id), inactive))
    await store.apply(ops)


def deactivate_lease_ops(lease: dict[str, Any]) -> list[StoreOp]:
    """Return the writes that mark ``lease`` inactive."""
    inactive = dict(lease)
    inactive["active"] = False
    lease_id = str(inactive["lease_id"])
    return [
        Put(lease_key(lease_id), inactive),
        SetRemove(LEASES_SET, lease_id),
        IndexRemove(expiry_mod.LEASES, lease_id),
    ]


def lease_is_active(record: dict[str, Any], now: datetime) -> bool:
    """Return True when the lease is active and has not expired."""
    if not record.get("active"):
        return False
    return parse_timestamp(record["expires_at"]) > now


def new_lease_id() -> str:
    """Return a new lease UUID."""
    return new_uuid()
