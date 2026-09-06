"""Atomic reply acceptance: response Message, Ticket, Thread, and lease ack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.tickets as tickets_mod
import agentconnect.team.threads as threads_mod
import agentconnect.team.trace as trace_mod
from agentconnect.team.errors import IDENTITY_MISSING
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import Cas, DeleteIfVersion, Insert, StoreOp


@dataclass
class ReplyCommit:
    """Inputs for one reply acceptance transition."""

    reply_id: str
    sender: str
    membership_id: str
    reply_hash: str
    reply_message: dict[str, Any]
    ticket: dict[str, Any]
    ticket_version: int
    mailbox_address: str
    mailbox_message_id: str
    mailbox_version: int
    lease: dict[str, Any]
    retention_seconds: float
    thread_limit: int
    now_ts: str
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReplyAccepted:
    """Committed reply result. Waiters are notified after this returns."""

    result: dict[str, Any]
    replay: bool
    events: list[dict[str, Any]]


class ReplyConflict(Exception):
    """Reply acceptance hit a named Runtime error."""

    def __init__(self, code: str, message: str) -> None:
        """Set the public ``code`` and ``message`` for this failure."""
        super().__init__(message)
        self.code = code
        self.message = message


async def load_reply_replay(
    store: Store,
    reply_id: str,
    reply_hash: str,
    membership_id: str,
) -> Optional[dict[str, Any]]:
    """Return a stored reply result when this id is already accepted."""
    existing = await store.get(f"reply:{reply_id}")
    if existing is None:
        return None
    if existing.get("membership_id") != membership_id:
        raise ReplyConflict("id_conflict", "Message id is already used")
    if existing.get("hash") != reply_hash:
        raise ReplyConflict(
            "id_conflict", "Message id is already used with different data"
        )
    result = existing.get("result")
    if isinstance(result, dict):
        return dict(result)
    return None


async def commit_reply(store: Store, commit: ReplyCommit) -> ReplyAccepted:
    """Commit reply acceptance or raise ``ReplyConflict``."""
    replay = await load_reply_replay(
        store, commit.reply_id, commit.reply_hash, commit.membership_id
    )
    if replay is not None:
        return ReplyAccepted(result=replay, replay=True, events=[])

    existing_msg = await store.get(f"msg:{commit.reply_id}")
    if existing_msg is not None:
        raise ReplyConflict("id_conflict", "Message id is already used")

    while True:
        ops, result, events = await _plan_reply(store, commit)
        applied = await store.apply(ops)
        if applied.ok:
            return ReplyAccepted(result=result, replay=False, events=events)
        if applied.reason == "exists":
            failed = ops[applied.op_index] if applied.op_index is not None else None
            key = getattr(failed, "key", "")
            if key.startswith(("msg:", "reply:")):
                replayed = await load_reply_replay(
                    store,
                    commit.reply_id,
                    commit.reply_hash,
                    commit.membership_id,
                )
                if replayed is not None:
                    return ReplyAccepted(result=replayed, replay=True, events=[])
                raise ReplyConflict("id_conflict", "Message id is already used")
            continue
        if applied.reason == "cas":
            failed = ops[applied.op_index] if applied.op_index is not None else None
            if isinstance(failed, DeleteIfVersion):
                raise ReplyConflict(
                    "lease_expired", "Delivery lease is no longer active"
                )
            if isinstance(failed, Cas) and str(failed.key).startswith("ticket:"):
                raise ReplyConflict("ticket_closed", "Ticket is already terminal")
            continue
        raise ReplyConflict("internal", "reply acceptance failed")


async def _plan_reply(
    store: Store, commit: ReplyCommit
) -> tuple[list[StoreOp], dict[str, Any], list[dict[str, Any]]]:
    message = dict(commit.reply_message)
    ops: list[StoreOp] = []
    keep_ids = await tickets_mod.retained_message_ids(store)
    keep_ids.add(commit.reply_id)
    keep_ids.add(str(commit.ticket["id"]))
    thread_id = message.get("thread_id")
    if isinstance(thread_id, str):
        record = await store.get_record(threads_mod.thread_key(thread_id))
        sender_mid = message.get("sender_membership_id")
        recipient_mid = message.get("recipient_membership_id")
        if not isinstance(sender_mid, str) or not sender_mid:
            raise ReplyConflict("internal", IDENTITY_MISSING)
        if not isinstance(recipient_mid, str) or not recipient_mid:
            raise ReplyConflict("internal", IDENTITY_MISSING)
        _thread, thread_ops, error = threads_mod.prepare_append(
            record,
            thread_id=thread_id,
            message=message,
            sender=sender_mid,
            recipient=recipient_mid,
            max_messages=commit.thread_limit,
            keep_ids=keep_ids,
        )
        if error == "forbidden":
            raise ReplyConflict(
                "forbidden", "Message is outside this Thread's participant set"
            )
        ops.extend(thread_ops)

    ticket = dict(commit.ticket)
    if "response" in ticket:
        ticket["response"] = message
    result = {"ticket": ticket}
    ops.extend(
        [
            Insert(f"msg:{commit.reply_id}", message),
            Insert(
                f"reply:{commit.reply_id}",
                {
                    "sender": commit.sender,
                    "membership_id": commit.membership_id,
                    "hash": commit.reply_hash,
                    "result": result,
                },
            ),
        ]
    )
    ops.extend(
        tickets_mod.cas_ticket_ops(
            ticket,
            commit.ticket_version,
            retention_seconds=commit.retention_seconds,
        )
    )
    ops.extend(
        mailbox_mod.acknowledge_ops(
            commit.mailbox_address,
            commit.mailbox_message_id,
            commit.mailbox_version,
        )
    )
    ops.extend(mailbox_mod.deactivate_lease_ops(commit.lease))
    events = list(commit.events)
    if events:
        trace_id = str(events[0]["trace_id"])
        trace_record = await store.get_record(trace_mod.trace_key(trace_id))
        ops.extend(trace_mod.append_event_ops(trace_record, events))
    return ops, result, events
