"""Atomic reply acceptance: response Message, Ticket, Thread, and lease ack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import agentconnect.team.expiry as expiry_mod
import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.retention as retention_mod
import agentconnect.team.tickets as tickets_mod
import agentconnect.team.threads as threads_mod
import agentconnect.team.trace as trace_mod
from agentconnect.team.codec import timestamp_score
from agentconnect.team.errors import IDENTITY_MISSING
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import Cas, DeleteIfVersion, IndexAdd, Insert, StoreOp


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
    replay_horizon_seconds: float
    retained_bytes_limit: int
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


async def assemble_reply_result(
    store: Store, record: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Build the public reply result from the Ticket and canonical body."""
    nested = record.get("result")
    if isinstance(nested, dict) and isinstance(nested.get("ticket"), dict):
        return dict(nested)
    ticket_id = record.get("ticket_id")
    if not isinstance(ticket_id, str):
        return None
    ticket = await tickets_mod.load_ticket(store, ticket_id)
    if ticket is None:
        return None
    return {"ticket": await tickets_mod.hydrate_ticket(store, ticket)}


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
    return await assemble_reply_result(store, existing)


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


def _public_reply_ticket(
    ticket: dict[str, Any], message: dict[str, Any]
) -> dict[str, Any]:
    out = dict(ticket)
    out.pop("result_message_id", None)
    if out.get("state") == "completed":
        out["response"] = message
    return out


async def _plan_reply(
    store: Store, commit: ReplyCommit
) -> tuple[list[StoreOp], dict[str, Any], list[dict[str, Any]]]:
    message = dict(commit.reply_message)
    ops: list[StoreOp] = []
    protect = {commit.reply_id, str(commit.ticket["id"])}
    dropped: list[str] = []
    thread_id = message.get("thread_id")
    if isinstance(thread_id, str):
        record = await store.get_record(threads_mod.thread_key(thread_id))
        sender_mid = message.get("sender_membership_id")
        recipient_mid = message.get("recipient_membership_id")
        if not isinstance(sender_mid, str) or not sender_mid:
            raise ReplyConflict("internal", IDENTITY_MISSING)
        if not isinstance(recipient_mid, str) or not recipient_mid:
            raise ReplyConflict("internal", IDENTITY_MISSING)
        thread, thread_ops, error = threads_mod.prepare_append(
            record,
            thread_id=thread_id,
            message=message,
            sender=sender_mid,
            recipient=recipient_mid,
            max_messages=commit.thread_limit,
        )
        if error == "forbidden":
            raise ReplyConflict(
                "forbidden", "Message is outside this Thread's participant set"
            )
        kept, dropped = await threads_mod.drop_unprotected_ids(
            store,
            list(thread.get("message_ids") or []),
            max_messages=commit.thread_limit,
            protect=protect,
        )
        thread["message_ids"] = kept
        ops.extend(thread_ops)

    ticket = dict(commit.ticket)
    result = {"ticket": _public_reply_ticket(ticket, message)}
    ops.extend(
        [
            Insert(f"msg:{commit.reply_id}", message),
            Insert(
                f"reply:{commit.reply_id}",
                {
                    "sender": commit.sender,
                    "membership_id": commit.membership_id,
                    "hash": commit.reply_hash,
                    "ticket_id": str(ticket["id"]),
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
    until = retention_mod.obligation_retain_until(
        commit.now_ts,
        horizon_seconds=commit.replay_horizon_seconds,
        ticket=ticket,
    )
    ops.extend(mailbox_mod.deactivate_lease_ops(commit.lease, retain_until=until))
    body_ops, freed = await retention_mod.release_body_deletes(
        store,
        dropped,
        ignore=retention_mod.IgnoreOwners(thread=True),
    )
    live_ops, live_freed = await retention_mod.release_body_deletes(
        store,
        [commit.mailbox_message_id],
        ignore=retention_mod.IgnoreOwners(live=True),
    )
    ops.extend(body_ops)
    ops.extend(live_ops)
    added = retention_mod.message_bytes(message)
    byte_ops = await retention_mod.plan_retained_bytes(
        store, added - freed - live_freed, commit.retained_bytes_limit
    )
    if byte_ops is None:
        raise ReplyConflict("busy", "Team retained storage is full")
    ops.extend(byte_ops)
    events = list(commit.events)
    if events:
        trace_id = str(events[0]["trace_id"])
        trace_record = await store.get_record(trace_mod.trace_key(trace_id))
        ops.extend(trace_mod.append_event_ops(trace_record, events))
        ops.append(IndexAdd(expiry_mod.TRACES, timestamp_score(until), trace_id))
    return ops, result, events
