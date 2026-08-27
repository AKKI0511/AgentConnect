"""Mailbox queue helpers.

A Mailbox is one logical queue per Membership. The Runtime puts accepted
Messages here; Sessions pull them with ``lease``. Depth counts queued and
leased items. Completing or replying removes the item.
"""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.team.codec import new_uuid, parse_timestamp
from agentconnect.team.store.base import Store

MAILBOX_KEY_PREFIX = "mailbox:"
LEASE_KEY_PREFIX = "lease:"
LEASES_SET = "leases"


def mailbox_key(address: str) -> str:
    """Return the store key for a Membership Mailbox."""
    return f"{MAILBOX_KEY_PREFIX}{address}"


def lease_key(lease_id: str) -> str:
    """Return the store key for a Delivery lease record."""
    return f"{LEASE_KEY_PREFIX}{lease_id}"


async def load_mailbox(store: Store, address: str) -> list[dict[str, Any]]:
    """Load the Mailbox queue for ``address``, or an empty list."""
    items = await store.get(mailbox_key(address))
    if items is None:
        return []
    return list(items)


async def save_mailbox(store: Store, address: str, items: list[dict[str, Any]]) -> None:
    """Persist the Mailbox queue for ``address``."""
    await store.put(mailbox_key(address), items)


def mailbox_depth(items: list[dict[str, Any]]) -> int:
    """Return queued plus leased item count."""
    return len(items)


def enqueue_item(items: list[dict[str, Any]], message_id: str, now_ts: str) -> None:
    """Append a queued Mailbox item for ``message_id``."""
    items.append(
        {
            "message_id": message_id,
            "enqueued_at": now_ts,
            "available_at": now_ts,
            "attempt": 0,
            "state": "queued",
            "lease_id": None,
            "lease_expires_at": None,
        }
    )


def find_item(items: list[dict[str, Any]], message_id: str) -> Optional[dict[str, Any]]:
    """Return the Mailbox item for ``message_id``, if present."""
    for item in items:
        if item["message_id"] == message_id:
            return item
    return None


def remove_item(
    items: list[dict[str, Any]], message_id: str
) -> Optional[dict[str, Any]]:
    """Remove and return the Mailbox item for ``message_id``."""
    for index, item in enumerate(items):
        if item["message_id"] == message_id:
            return items.pop(index)
    return None


def release_lease_on_item(item: dict[str, Any], now_ts: str) -> None:
    """Return a leased item to the queue after lease or Session loss."""
    item["state"] = "queued"
    item["available_at"] = now_ts
    item["lease_id"] = None
    item["lease_expires_at"] = None


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
    await store.put(lease_key(lease_id), record)
    await store.set_add(LEASES_SET, lease_id)
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
    if record is not None:
        record["active"] = False
        await store.put(lease_key(lease_id), record)
    await store.set_remove(LEASES_SET, lease_id)


def lease_is_active(record: dict[str, Any], now) -> bool:
    """Return True when the lease is active and has not expired."""
    if not record.get("active"):
        return False
    return parse_timestamp(record["expires_at"]) > now


def new_lease_id() -> str:
    """Return a new lease UUID."""
    return new_uuid()


def expire_item_if_needed(item: dict[str, Any], now, now_ts: str) -> Optional[str]:
    """If the item's lease has passed, return it to queued and yield the lease id."""
    if item.get("state") != "leased":
        return None
    expires = item.get("lease_expires_at")
    if expires is None:
        return None
    if parse_timestamp(expires) > now:
        return None
    lease_id = item.get("lease_id")
    release_lease_on_item(item, now_ts)
    return lease_id
