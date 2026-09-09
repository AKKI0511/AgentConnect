"""Ticket records stored by the Runtime.

A Ticket is the requester's durable result record. Its id equals the
request Message id. The only transitions are open to a terminal state.
The first accepted reply wins; a later distinct reply increments
``late_reply_count`` and does not replace the outcome.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from agentconnect.team.codec import format_timestamp, parse_timestamp, timestamp_score
from agentconnect.team.constants import TICKET_TERMINAL
import agentconnect.team.expiry as expiry_mod
from agentconnect.team.store.base import Store, StoreRecord
from agentconnect.team.retention import RETAIN_MESSAGES_SET, open_ticket_count_key
from agentconnect.team.store.ops import (
    Cas,
    DecrementFloor,
    DeleteIfVersion,
    IndexAdd,
    IndexRemove,
    Insert,
    SetAdd,
    SetRemove,
    StoreOp,
)

TICKET_KEY_PREFIX = "ticket:"
OPEN_TICKETS_SET = "tickets:open"
ALL_TICKETS_SET = "tickets"


def ticket_key(ticket_id: str) -> str:
    """Return the store key for a Ticket record."""
    return f"{TICKET_KEY_PREFIX}{ticket_id}"


def is_terminal(ticket: dict[str, Any]) -> bool:
    """Return True when the Ticket is in a terminal state."""
    return ticket.get("state") in TICKET_TERMINAL


def new_open_ticket(
    *,
    ticket_id: str,
    requester: str,
    recipient: str,
    created_at: str,
    deadline: str,
    requester_membership_id: str,
    recipient_membership_id: str,
    thread_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build an open Ticket whose id is the request Message id."""
    ticket: dict[str, Any] = {
        "id": ticket_id,
        "requester": requester,
        "recipient": recipient,
        "state": "open",
        "created_at": created_at,
        "updated_at": created_at,
        "deadline": deadline,
        "late_reply_count": 0,
        "requester_membership_id": requester_membership_id,
        "recipient_membership_id": recipient_membership_id,
    }
    if thread_id is not None:
        ticket["thread_id"] = thread_id
    return ticket


def mark_completed(
    ticket: dict[str, Any], response: dict[str, Any], now_ts: str
) -> dict[str, Any]:
    """Mark the Ticket completed. The response body stays at ``msg:{id}``."""
    ticket = dict(ticket)
    ticket["state"] = "completed"
    ticket["updated_at"] = now_ts
    ticket["result_message_id"] = response["id"]
    ticket.pop("error", None)
    ticket.pop("response", None)
    return ticket


def mark_failed(
    ticket: dict[str, Any],
    error: dict[str, Any],
    now_ts: str,
    *,
    result_message_id: Optional[str] = None,
) -> dict[str, Any]:
    """Mark the Ticket failed with a handler error."""
    ticket = dict(ticket)
    ticket["state"] = "failed"
    ticket["updated_at"] = now_ts
    ticket["error"] = error
    ticket.pop("response", None)
    if result_message_id is not None:
        ticket["result_message_id"] = result_message_id
    return ticket


def mark_declined(ticket: dict[str, Any], now_ts: str) -> dict[str, Any]:
    """Mark the Ticket declined after complete on a request."""
    ticket = dict(ticket)
    ticket["state"] = "declined"
    ticket["updated_at"] = now_ts
    ticket.pop("response", None)
    ticket.pop("error", None)
    return ticket


def mark_expired(ticket: dict[str, Any], now_ts: str) -> dict[str, Any]:
    """Mark the Ticket expired after its deadline."""
    ticket = dict(ticket)
    ticket["state"] = "expired"
    ticket["updated_at"] = now_ts
    ticket["error"] = {
        "code": "deadline_exceeded",
        "message": "The request deadline passed before a reply was accepted.",
    }
    ticket.pop("response", None)
    return ticket


def observe_late_reply(ticket: dict[str, Any], now_ts: str) -> dict[str, Any]:
    """Count a reply that arrived after the Ticket was already terminal."""
    ticket = dict(ticket)
    ticket["late_reply_count"] = int(ticket.get("late_reply_count") or 0) + 1
    ticket["updated_at"] = now_ts
    return ticket


def deadline_passed(ticket: dict[str, Any], now) -> bool:
    """Return True when the Ticket deadline is at or before ``now``."""
    return parse_timestamp(ticket["deadline"]) <= now


def retain_until_ts(ticket: dict[str, Any], *, retention_seconds: float) -> str:
    """Return when a terminal Ticket may be deleted.

    Later of the request deadline and ``updated_at + retention_seconds``.
    """
    closed_at = parse_timestamp(ticket["updated_at"])
    deadline = parse_timestamp(ticket["deadline"])
    retain = max(deadline, closed_at + timedelta(seconds=float(retention_seconds)))
    return format_timestamp(retain)


def insert_ticket_ops(ticket: dict[str, Any]) -> list[StoreOp]:
    """Return the writes that create an open Ticket and its indexes."""
    ticket_id = ticket["id"]
    ops: list[StoreOp] = [
        Insert(ticket_key(ticket_id), ticket),
        SetAdd(ALL_TICKETS_SET, ticket_id),
    ]
    if ticket["state"] == "open":
        ops.extend(
            [
                SetAdd(OPEN_TICKETS_SET, ticket_id),
                IndexAdd(
                    expiry_mod.OPEN_TICKETS,
                    timestamp_score(ticket["deadline"]),
                    ticket_id,
                ),
                SetAdd(RETAIN_MESSAGES_SET, ticket_id),
            ]
        )
    return ops


def cas_ticket_ops(
    ticket: dict[str, Any],
    version: int,
    *,
    retention_seconds: Optional[float] = None,
) -> list[StoreOp]:
    """Return the writes that replace a Ticket at ``version``."""
    ticket_id = ticket["id"]
    ops: list[StoreOp] = [
        Cas(ticket_key(ticket_id), version, ticket),
        SetAdd(ALL_TICKETS_SET, ticket_id),
    ]
    if ticket["state"] == "open":
        ops.extend(
            [
                SetAdd(OPEN_TICKETS_SET, ticket_id),
                IndexAdd(
                    expiry_mod.OPEN_TICKETS,
                    timestamp_score(ticket["deadline"]),
                    ticket_id,
                ),
                SetAdd(RETAIN_MESSAGES_SET, ticket_id),
            ]
        )
    else:
        ops.extend(
            [
                SetRemove(OPEN_TICKETS_SET, ticket_id),
                IndexRemove(expiry_mod.OPEN_TICKETS, ticket_id),
            ]
        )
        if retention_seconds is not None:
            ops.append(
                IndexAdd(
                    expiry_mod.TERMINAL_TICKETS,
                    timestamp_score(
                        retain_until_ts(ticket, retention_seconds=retention_seconds)
                    ),
                    ticket_id,
                )
            )
            requester = ticket.get("requester_membership_id")
            if isinstance(requester, str) and requester:
                ops.append(DecrementFloor(open_ticket_count_key(requester)))
        result_id = ticket.get("result_message_id")
        if not isinstance(result_id, str):
            response = ticket.get("response")
            if isinstance(response, dict) and isinstance(response.get("id"), str):
                result_id = str(response["id"])
        if isinstance(result_id, str) and result_id:
            ops.append(SetAdd(RETAIN_MESSAGES_SET, result_id))
    return ops


async def retain_message(store: Store, message_id: str) -> None:
    """Keep ``message_id`` in Thread history while a Ticket still needs it."""
    await store.set_add(RETAIN_MESSAGES_SET, message_id)


async def drop_retained_message(store: Store, message_id: str) -> None:
    """Stop protecting ``message_id`` from Thread retention."""
    await store.set_remove(RETAIN_MESSAGES_SET, message_id)


async def retained_message_ids(store: Store) -> set[str]:
    """Return Message ids Thread trim must keep."""
    return set(await store.set_members(RETAIN_MESSAGES_SET))


async def save_ticket(store: Store, ticket: dict[str, Any]) -> None:
    """Persist a Ticket and update the open/all Ticket sets."""
    ticket_id = ticket["id"]
    await store.put(ticket_key(ticket_id), ticket)
    await store.set_add(ALL_TICKETS_SET, ticket_id)
    if ticket["state"] == "open":
        await store.set_add(OPEN_TICKETS_SET, ticket_id)
        await expiry_mod.schedule(
            store, expiry_mod.OPEN_TICKETS, ticket_id, ticket["deadline"]
        )
        await retain_message(store, ticket_id)
    else:
        await store.set_remove(OPEN_TICKETS_SET, ticket_id)
        await expiry_mod.cancel(store, expiry_mod.OPEN_TICKETS, ticket_id)


async def insert_ticket(store: Store, ticket: dict[str, Any]) -> bool:
    """Insert an open Ticket. False if that id already exists."""
    result = await store.apply(insert_ticket_ops(ticket))
    return result.ok


async def cas_ticket(
    store: Store,
    ticket: dict[str, Any],
    version: int,
    *,
    retention_seconds: Optional[float] = None,
) -> bool:
    """Replace a Ticket when ``version`` still matches.

    Pass ``retention_seconds`` when this write is the open-to-terminal
    transition so the sweep can pop the Ticket when retention ends.
    """
    result = await store.apply(
        cas_ticket_ops(ticket, version, retention_seconds=retention_seconds)
    )
    return result.ok


async def hydrate_ticket(store: Store, ticket: dict[str, Any]) -> dict[str, Any]:
    """Assemble the public Ticket, loading a completed response from ``msg:``."""
    out = dict(ticket)
    result_id = out.pop("result_message_id", None)
    if out.get("state") == "completed" and "response" not in out:
        if isinstance(result_id, str) and result_id:
            body = await store.get(f"msg:{result_id}")
            if isinstance(body, dict):
                out["response"] = body
    return out


async def load_ticket(store: Store, ticket_id: str) -> Optional[dict[str, Any]]:
    """Load a Ticket, or None if it is missing."""
    record = await store.get(ticket_key(ticket_id))
    if record is None:
        return None
    return record


async def load_ticket_record(store: Store, ticket_id: str) -> Optional[StoreRecord]:
    """Load a Ticket with its store version, or None if it is missing."""
    return await store.get_record(ticket_key(ticket_id))


def delete_ticket_ops(ticket: dict[str, Any], version: int) -> list[StoreOp]:
    """Return the writes that remove a Ticket and its indexes at ``version``."""
    ticket_id = str(ticket["id"])
    ops: list[StoreOp] = [
        DeleteIfVersion(ticket_key(ticket_id), version),
        SetRemove(OPEN_TICKETS_SET, ticket_id),
        SetRemove(ALL_TICKETS_SET, ticket_id),
        IndexRemove(expiry_mod.OPEN_TICKETS, ticket_id),
        IndexRemove(expiry_mod.TERMINAL_TICKETS, ticket_id),
        SetRemove(RETAIN_MESSAGES_SET, ticket_id),
    ]
    result_id = ticket.get("result_message_id")
    if not isinstance(result_id, str):
        response = ticket.get("response")
        if isinstance(response, dict) and isinstance(response.get("id"), str):
            result_id = str(response["id"])
    if isinstance(result_id, str) and result_id:
        ops.append(SetRemove(RETAIN_MESSAGES_SET, result_id))
    return ops


async def delete_ticket(store: Store, ticket_id: str) -> Optional[dict[str, Any]]:
    """Remove a Ticket, drop indexes, and return the deleted record if any."""
    record = await load_ticket_record(store, ticket_id)
    ticket = None if record is None else dict(record.value)
    if record is not None and ticket is not None:
        await store.apply(delete_ticket_ops(ticket, record.version))
        return ticket
    await store.delete(ticket_key(ticket_id))
    await store.set_remove(OPEN_TICKETS_SET, ticket_id)
    await store.set_remove(ALL_TICKETS_SET, ticket_id)
    await expiry_mod.cancel(store, expiry_mod.OPEN_TICKETS, ticket_id)
    await expiry_mod.cancel(store, expiry_mod.TERMINAL_TICKETS, ticket_id)
    await drop_retained_message(store, ticket_id)
    return ticket
