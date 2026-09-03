"""Ticket records stored by the Runtime.

A Ticket is the requester's durable result record. Its id equals the
request Message id. The only transitions are open to a terminal state.
The first accepted reply wins; a later distinct reply increments
``late_reply_count`` and does not replace the outcome.
"""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.team.codec import parse_timestamp
from agentconnect.team.constants import TICKET_TERMINAL
from agentconnect.team.store.base import Store

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
    }
    if thread_id is not None:
        ticket["thread_id"] = thread_id
    return ticket


def mark_completed(
    ticket: dict[str, Any], response: dict[str, Any], now_ts: str
) -> dict[str, Any]:
    """Mark the Ticket completed with the winning response Message."""
    ticket = dict(ticket)
    ticket["state"] = "completed"
    ticket["updated_at"] = now_ts
    ticket["response"] = response
    ticket.pop("error", None)
    return ticket


def mark_failed(
    ticket: dict[str, Any], error: dict[str, Any], now_ts: str
) -> dict[str, Any]:
    """Mark the Ticket failed with a handler error."""
    ticket = dict(ticket)
    ticket["state"] = "failed"
    ticket["updated_at"] = now_ts
    ticket["error"] = error
    ticket.pop("response", None)
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


async def save_ticket(store: Store, ticket: dict[str, Any]) -> None:
    """Persist a Ticket and update the open/all Ticket sets."""
    ticket_id = ticket["id"]
    await store.put(ticket_key(ticket_id), ticket)
    await store.set_add(ALL_TICKETS_SET, ticket_id)
    if ticket["state"] == "open":
        await store.set_add(OPEN_TICKETS_SET, ticket_id)
    else:
        await store.set_remove(OPEN_TICKETS_SET, ticket_id)


async def load_ticket(store: Store, ticket_id: str) -> Optional[dict[str, Any]]:
    """Load a Ticket, or None if it is missing."""
    record = await store.get(ticket_key(ticket_id))
    if record is None:
        return None
    return record


async def delete_ticket(store: Store, ticket_id: str) -> None:
    """Remove a Ticket and drop it from Ticket sets."""
    await store.delete(ticket_key(ticket_id))
    await store.set_remove(OPEN_TICKETS_SET, ticket_id)
    await store.set_remove(ALL_TICKETS_SET, ticket_id)
