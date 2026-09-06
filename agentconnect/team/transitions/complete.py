"""Atomic complete: Ticket decline (when a request), lease ack, stored result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.tickets as tickets_mod
import agentconnect.team.trace as trace_mod
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import Cas, DeleteIfVersion, Put, StoreOp


@dataclass
class CompleteCommit:
    """Inputs for one complete transition."""

    lease_id: str
    result: dict[str, Any]
    ticket: Optional[dict[str, Any]]
    ticket_version: Optional[int]
    mailbox_address: str
    mailbox_message_id: str
    mailbox_version: int
    lease: dict[str, Any]
    retention_seconds: float
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CompleteAccepted:
    """Committed complete result."""

    result: dict[str, Any]
    replay: bool
    events: list[dict[str, Any]]


class CompleteConflict(Exception):
    """Complete hit a named Runtime error."""

    def __init__(self, code: str, message: str) -> None:
        """Set the public ``code`` and ``message`` for this failure."""
        super().__init__(message)
        self.code = code
        self.message = message


async def load_complete_replay(store: Store, lease_id: str) -> Optional[dict[str, Any]]:
    """Return a stored complete result for this lease, if any."""
    existing = await store.get(f"complete:{lease_id}")
    if existing is None:
        return None
    result = existing.get("result")
    if isinstance(result, dict):
        return dict(result)
    return existing if isinstance(existing, dict) else None


async def commit_complete(store: Store, commit: CompleteCommit) -> CompleteAccepted:
    """Commit complete or raise ``CompleteConflict``."""
    replay = await load_complete_replay(store, commit.lease_id)
    if replay is not None:
        return CompleteAccepted(result=replay, replay=True, events=[])

    while True:
        ops, result, events = await _plan_complete(store, commit)
        applied = await store.apply(ops)
        if applied.ok:
            return CompleteAccepted(result=result, replay=False, events=events)
        if applied.reason == "cas":
            failed = ops[applied.op_index] if applied.op_index is not None else None
            if isinstance(failed, DeleteIfVersion):
                replayed = await load_complete_replay(store, commit.lease_id)
                if replayed is not None:
                    return CompleteAccepted(result=replayed, replay=True, events=[])
                raise CompleteConflict(
                    "lease_expired", "Delivery lease is no longer active"
                )
            if isinstance(failed, Cas) and str(failed.key).startswith("ticket:"):
                raise CompleteConflict("ticket_closed", "Ticket is already terminal")
            continue
        raise CompleteConflict("internal", "complete failed")


async def _plan_complete(
    store: Store, commit: CompleteCommit
) -> tuple[list[StoreOp], dict[str, Any], list[dict[str, Any]]]:
    ops: list[StoreOp] = [
        Put(f"complete:{commit.lease_id}", {"result": commit.result}),
    ]
    if commit.ticket is not None and commit.ticket_version is not None:
        ops.extend(
            tickets_mod.cas_ticket_ops(
                commit.ticket,
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
    return ops, commit.result, events
