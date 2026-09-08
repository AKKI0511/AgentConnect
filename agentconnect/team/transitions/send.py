"""Atomic send acceptance: Message, Ticket, Thread, then a leaseable Mailbox item."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.tickets as tickets_mod
import agentconnect.team.threads as threads_mod
import agentconnect.team.trace as trace_mod
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import IncrementIfBelow, Insert, StoreOp


@dataclass
class SendCommit:
    """Inputs for one send acceptance transition."""

    message_id: str
    sender: str
    membership_id: str
    recipient: str
    recipient_membership_id: str
    collect: Optional[str]
    request_hash: str
    message: dict[str, Any]
    ticket: Optional[dict[str, Any]]
    max_depth: int
    max_held_waits: int
    thread_limit: int
    wait_ttl: float
    now_ts: str
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SendAccepted:
    """Committed send result. Hints are published after this returns."""

    result: dict[str, Any]
    replay: bool
    wait: bool
    events: list[dict[str, Any]]


class SendConflict(Exception):
    """Send acceptance hit a named Runtime error."""

    def __init__(self, code: str, message: str) -> None:
        """Set the public ``code`` and ``message`` for this failure."""
        super().__init__(message)
        self.code = code
        self.message = message


async def load_replay(
    store: Store,
    message_id: str,
    membership_id: str,
    request_hash: str,
) -> Optional[dict[str, Any]]:
    """Return a stored send result when this id is already accepted."""
    existing = await store.get(f"send:{message_id}")
    if existing is None:
        return None
    if existing.get("membership_id") != membership_id:
        raise SendConflict("id_conflict", "Message id is already used")
    if existing.get("hash") != request_hash:
        raise SendConflict(
            "id_conflict", "Message id is already used with different data"
        )
    result = existing.get("result")
    if isinstance(result, dict):
        return dict(result)
    return None


async def commit_send(store: Store, commit: SendCommit) -> SendAccepted:
    """Commit send acceptance or raise ``SendConflict``.

    The Mailbox item becomes leaseable only when this returns. A conflict
    or crash leaves either the full accepted state or no acceptance.
    """
    replay = await load_replay(
        store, commit.message_id, commit.membership_id, commit.request_hash
    )
    if replay is not None:
        return SendAccepted(result=replay, replay=True, wait=False, events=[])

    while True:
        ops, result, events = await _plan_send(store, commit)
        applied = await store.apply(ops)
        if applied.ok:
            return SendAccepted(
                result=result,
                replay=False,
                wait=commit.collect == "wait",
                events=events,
            )
        if applied.reason == "busy":
            raise SendConflict("busy", "Recipient Mailbox is full")
        if applied.reason == "limit":
            raise SendConflict(
                "wait_limit",
                "this Membership already holds the maximum number of waits",
            )
        if applied.reason == "exists":
            failed = ops[applied.op_index] if applied.op_index is not None else None
            key = getattr(failed, "key", "")
            reserved = key.startswith(("send:", "msg:", "ticket:")) or ":item:" in key
            if reserved:
                replayed = await load_replay(
                    store,
                    commit.message_id,
                    commit.membership_id,
                    commit.request_hash,
                )
                if replayed is not None:
                    return SendAccepted(
                        result=replayed, replay=True, wait=False, events=[]
                    )
                raise SendConflict("id_conflict", "Message id is already used")
            continue
        if applied.reason == "cas":
            continue
        raise SendConflict("internal", "send acceptance failed")


async def _plan_send(
    store: Store, commit: SendCommit
) -> tuple[list[StoreOp], dict[str, Any], list[dict[str, Any]]]:
    message = dict(commit.message)
    ops: list[StoreOp] = []
    if commit.collect == "wait":
        ops.append(
            IncrementIfBelow(
                f"held_waits:{commit.membership_id}",
                commit.max_held_waits,
                ttl_seconds=commit.wait_ttl,
            )
        )

    keep_ids = await tickets_mod.retained_message_ids(store)
    keep_ids.add(commit.message_id)
    thread_id = message.get("thread_id")
    if isinstance(thread_id, str):
        record = await store.get_record(threads_mod.thread_key(thread_id))
        _thread, thread_ops, error = threads_mod.prepare_append(
            record,
            thread_id=thread_id,
            message=message,
            sender=commit.membership_id,
            recipient=commit.recipient_membership_id,
            max_messages=commit.thread_limit,
            keep_ids=keep_ids,
        )
        if error == "forbidden":
            raise SendConflict(
                "forbidden", "Message is outside this Thread's participant set"
            )
        ops.extend(thread_ops)

    if commit.ticket is not None:
        result: dict[str, Any] = {
            "status": "ticketed",
            "message": message,
            "ticket": commit.ticket,
        }
    else:
        result = {"status": "accepted", "message": message}

    send_record = {
        "sender": commit.sender,
        "membership_id": commit.membership_id,
        "hash": commit.request_hash,
        "collect": commit.collect,
        "result": result,
    }
    ops.extend(
        [
            Insert(f"send:{commit.message_id}", send_record),
            Insert(f"msg:{commit.message_id}", message),
        ]
    )
    if commit.ticket is not None:
        ops.extend(tickets_mod.insert_ticket_ops(commit.ticket))
    ops.extend(
        mailbox_mod.enqueue_ops(
            commit.recipient,
            commit.message_id,
            commit.now_ts,
            max_depth=commit.max_depth,
        )
    )

    events = list(commit.events)
    if events:
        trace_id = str(events[0]["trace_id"])
        trace_record = await store.get_record(trace_mod.trace_key(trace_id))
        ops.extend(trace_mod.append_event_ops(trace_record, events))

    return ops, result, events
