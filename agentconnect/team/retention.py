"""Owners and byte accounting for retained Runtime records.

One document at ``msg:{id}`` is the Message body. Delivery, Thread,
Ticket, and replay records name that id. Public results are assembled
on read.

A body stays while any of these still names it:

- live work: a queued or leased Mailbox item (``live:messages``)
- a Ticket still inside its promised replay window (``retain:messages``)
- a send or reply replay record
- a remaining Thread history entry

Thread count trim may drop an id from history only when it is not live
work and not Ticket-retained. Replay expiry may drop a replay record
without cancelling outstanding delivery. Reclaim deletes the body,
references, reservations, indexes, and byte counter together, or leaves
the index entries so the next sweep retries. A failed compare-and-set is
never treated as successful cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Coroutine, Optional

from agentconnect.team.codec import format_timestamp, json_size, parse_timestamp
import agentconnect.team.expiry as expiry_mod
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import (
    Cas,
    Delete,
    IndexRemove,
    Insert,
    SetRemove,
    StoreOp,
)

RETAINED_BYTES_KEY = "stats:retained_bytes"
OPEN_TICKETS_COUNT_PREFIX = "open_tickets:"
LIVE_MESSAGES_SET = "live:messages"
RETAIN_MESSAGES_SET = "retain:messages"


@dataclass(frozen=True)
class IgnoreOwners:
    """Owners this reclaim is already deleting in the same apply."""

    live: bool = False
    ticket: bool = False
    send: bool = False
    reply: bool = False
    thread: bool = False


def open_ticket_count_key(membership_id: str) -> str:
    """Return the integer document that counts open Tickets for a requester."""
    return f"{OPEN_TICKETS_COUNT_PREFIX}{membership_id}"


def replay_until(now_ts: str, *, horizon_seconds: float) -> str:
    """Return ``now_ts + horizon_seconds`` as a Runtime timestamp."""
    instant = parse_timestamp(now_ts) + timedelta(seconds=float(horizon_seconds))
    return format_timestamp(instant)


def obligation_retain_until(
    now_ts: str,
    *,
    horizon_seconds: float,
    ticket: Optional[dict[str, Any]] = None,
) -> str:
    """Return when request complete/reply replay may be deleted.

    Requests use the later of the Ticket deadline and the horizon after
    close. Events use ``now_ts + horizon_seconds``.
    """
    if ticket is None:
        return replay_until(now_ts, horizon_seconds=horizon_seconds)
    import agentconnect.team.tickets as tickets_mod

    return tickets_mod.retain_until_ts(ticket, retention_seconds=horizon_seconds)


async def plan_retained_bytes(
    store: Store,
    delta: int,
    limit: int,
) -> Optional[list[StoreOp]]:
    """Return writes that add ``delta`` to the Message-body byte counter.

    ``None`` means a positive ``delta`` would pass ``limit``.

        ops = await plan_retained_bytes(store, json_size(message), limit)
        if ops is None:
            raise SendConflict("busy", "Team retained storage is full")
    """
    if delta == 0:
        return []
    record = await store.get_record(RETAINED_BYTES_KEY)
    current = 0 if record is None else int(record.value or 0)
    nxt = current + int(delta)
    if nxt < 0:
        nxt = 0
    if delta > 0 and nxt > int(limit):
        return None
    if record is None:
        return [Insert(RETAINED_BYTES_KEY, nxt)]
    return [Cas(RETAINED_BYTES_KEY, record.version, nxt)]


def message_bytes(value: Any) -> int:
    """Return the UTF-8 JSON size of a stored Message body."""
    if not isinstance(value, dict):
        return 0
    return json_size(value)


async def sizes_of(store: Store, message_ids: list[str]) -> int:
    """Return the stored JSON size of ``message_ids`` that still exist."""
    if not message_ids:
        return 0
    records = await store.get_many([f"msg:{item}" for item in message_ids])
    return sum(message_bytes(item) for item in records)


async def is_live_work(store: Store, message_id: str) -> bool:
    """Return True when a Mailbox item still queues or leases ``message_id``."""
    return await store.set_is_member(LIVE_MESSAGES_SET, message_id)


async def is_ticket_retained(store: Store, message_id: str) -> bool:
    """Return True when a Ticket still needs ``message_id``."""
    return await store.set_is_member(RETAIN_MESSAGES_SET, message_id)


async def _thread_lists(store: Store, message_id: str, stored: Any) -> bool:
    if not isinstance(stored, dict):
        return False
    thread_id = stored.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id:
        return False
    thread = await store.get(f"thread:{thread_id}")
    if not isinstance(thread, dict):
        return False
    ids = thread.get("message_ids")
    return isinstance(ids, list) and message_id in ids


async def has_remaining_owner(
    store: Store,
    message_id: str,
    *,
    ignore: IgnoreOwners = IgnoreOwners(),
    stored: Any = None,
) -> bool:
    """Return True when another owner still needs ``msg:{id}``."""
    if not ignore.live and await is_live_work(store, message_id):
        return True
    if not ignore.ticket and await is_ticket_retained(store, message_id):
        return True
    if not ignore.send and await store.get(f"send:{message_id}") is not None:
        return True
    if not ignore.reply and await store.get(f"reply:{message_id}") is not None:
        return True
    if not ignore.thread:
        body = stored if stored is not None else await store.get(f"msg:{message_id}")
        if await _thread_lists(store, message_id, body):
            return True
    return False


async def release_body_deletes(
    store: Store,
    message_ids: list[str],
    *,
    ignore: IgnoreOwners,
) -> tuple[list[StoreOp], int]:
    """Return deletes for bodies that no remaining owner needs, plus bytes freed."""
    ops: list[StoreOp] = []
    freed = 0
    seen: set[str] = set()
    for message_id in message_ids:
        if message_id in seen:
            continue
        seen.add(message_id)
        stored = await store.get(f"msg:{message_id}")
        if stored is None:
            continue
        if await has_remaining_owner(store, message_id, ignore=ignore, stored=stored):
            continue
        ops.append(Delete(f"msg:{message_id}"))
        freed += message_bytes(stored)
    return ops, freed


async def plan_release_ops(
    store: Store,
    message_ids: list[str],
    *,
    byte_limit: int,
    ignore: IgnoreOwners = IgnoreOwners(),
) -> list[StoreOp]:
    """Return body deletes and the matching byte-counter write."""
    ops, freed = await release_body_deletes(store, message_ids, ignore=ignore)
    if freed:
        byte_ops = await plan_retained_bytes(store, -freed, byte_limit)
        if byte_ops:
            ops.extend(byte_ops)
    return ops


async def reclaim_unowned_bodies(
    store: Store,
    message_ids: list[str],
    *,
    byte_limit: int,
    ignore: IgnoreOwners = IgnoreOwners(),
) -> None:
    """Delete unowned bodies, retrying a byte-counter compare-and-set."""

    async def plan() -> list[StoreOp]:
        return await plan_release_ops(
            store, message_ids, byte_limit=byte_limit, ignore=ignore
        )

    await _apply_reclaim(store, plan)


async def _apply_reclaim(
    store: Store,
    plan: Callable[[], Coroutine[Any, Any, list[StoreOp]]],
) -> None:
    """Commit ``plan()`` or retry a compare-and-set conflict.

    Any other apply failure leaves the store unchanged so a later sweep
    can retry. The caller must not assume cleanup succeeded.
    """
    while True:
        ops = await plan()
        if not ops:
            return
        applied = await store.apply(ops)
        if applied.ok:
            return
        if applied.reason == "cas":
            continue
        return


async def reclaim_event_replay(
    store: Store, message_id: str, *, byte_limit: int
) -> None:
    """Drop an event send replay once its horizon has elapsed.

    The Message body stays when live work, a Ticket, a reply record, or
    Thread history still names it. Reuse of the id then fails with
    ``id_conflict`` until those owners release it.
    """

    async def plan() -> list[StoreOp]:
        ops: list[StoreOp] = [
            Delete(f"send:{message_id}"),
            IndexRemove(expiry_mod.REPLAYS, message_id),
        ]
        ops.extend(
            await plan_release_ops(
                store,
                [message_id],
                byte_limit=byte_limit,
                ignore=IgnoreOwners(send=True),
            )
        )
        return ops

    await _apply_reclaim(store, plan)


def _ticket_result_id(ticket: dict[str, Any]) -> Optional[str]:
    result_id = ticket.get("result_message_id")
    if isinstance(result_id, str) and result_id:
        return result_id
    response = ticket.get("response")
    if isinstance(response, dict) and isinstance(response.get("id"), str):
        return str(response["id"])
    return None


async def reclaim_ticket_records(
    store: Store,
    ticket: dict[str, Any],
    *,
    byte_limit: int,
) -> list[str]:
    """Drop a Ticket and its replay records in one apply.

    Request and result bodies are deleted only when no other owner still
    names them. A failed byte-counter compare-and-set retries the whole
    batch, including the Ticket delete.
    """
    import agentconnect.team.tickets as tickets_mod

    ticket_id = str(ticket["id"])
    dropped: list[str] = []

    async def plan() -> list[StoreOp]:
        dropped.clear()
        record = await tickets_mod.load_ticket_record(store, ticket_id)
        ops: list[StoreOp] = [
            Delete(f"send:{ticket_id}"),
            IndexRemove(expiry_mod.TERMINAL_TICKETS, ticket_id),
            IndexRemove(expiry_mod.OPEN_TICKETS, ticket_id),
            IndexRemove(expiry_mod.REPLAYS, ticket_id),
            SetRemove(RETAIN_MESSAGES_SET, ticket_id),
        ]
        reply_id = _ticket_result_id(ticket)
        if record is not None:
            current = dict(record.value)
            reply_id = _ticket_result_id(current)
            ops.extend(tickets_mod.delete_ticket_ops(current, record.version))
        if reply_id is not None:
            ops.append(Delete(f"reply:{reply_id}"))
            ops.append(IndexRemove(expiry_mod.REPLAYS, reply_id))
            ops.append(SetRemove(RETAIN_MESSAGES_SET, reply_id))
        candidates = [ticket_id]
        if reply_id is not None:
            candidates.append(reply_id)
        release_ops = await plan_release_ops(
            store,
            candidates,
            byte_limit=byte_limit,
            ignore=IgnoreOwners(ticket=True, send=True, reply=True),
        )
        ops.extend(release_ops)
        dropped.extend(
            item
            for item in candidates
            if any(
                isinstance(op, Delete) and op.key == f"msg:{item}" for op in release_ops
            )
        )
        return ops

    await _apply_reclaim(store, plan)
    return list(dropped)


async def reclaim_inactive_lease(
    store: Store, lease_id: str, *, byte_limit: int
) -> None:
    """Drop an inactive lease, its complete replay, and an unowned body.

    Complete replay is not a Message-body owner. If live work and send
    replay already ended, this sweep is the recoverable reclaim for the
    body and its byte charge.
    """

    async def plan() -> list[StoreOp]:
        lease = await store.get(f"lease:{lease_id}")
        ops: list[StoreOp] = [
            Delete(f"lease:{lease_id}"),
            Delete(f"complete:{lease_id}"),
            IndexRemove(expiry_mod.INACTIVE_LEASES, lease_id),
        ]
        message_id = None
        if isinstance(lease, dict) and isinstance(lease.get("message_id"), str):
            message_id = str(lease["message_id"])
        if message_id is not None:
            ops.extend(
                await plan_release_ops(store, [message_id], byte_limit=byte_limit)
            )
        return ops

    await _apply_reclaim(store, plan)


async def reclaim_trace(store: Store, trace_id: str) -> None:
    """Drop a Trace when none of its named Messages remain."""
    events = await store.get(f"trace:{trace_id}")
    ids: list[str] = []
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict) and isinstance(event.get("message_id"), str):
                ids.append(str(event["message_id"]))
    remaining = await store.get_many([f"msg:{item}" for item in ids])
    if any(item is not None for item in remaining):
        return
    await store.apply(
        [
            Delete(f"trace:{trace_id}"),
            IndexRemove(expiry_mod.TRACES, trace_id),
        ]
    )
