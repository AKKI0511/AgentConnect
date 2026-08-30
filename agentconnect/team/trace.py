"""Trace timeline stored by the Team Runtime.

A Trace is one causal operation. ``get_trace`` returns the events the
Runtime recorded for a ``trace_id``. The store is the same one that holds
Messages and Tickets, so a Redis Team keeps the timeline across restart.

    token = await team.ensure_operator_session()
    result = await team.get_trace(token, message["trace_id"])
    types = [event["type"] for event in result["events"]]
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from agentconnect.team.store.base import Store

TRACE_KEY_PREFIX = "trace:"
TRACES_SET = "traces"
MAX_TRACE_EVENTS = 200

EVENT_TYPES = frozenset(
    {
        "accepted",
        "ticket_opened",
        "leased",
        "completed",
        "replied",
        "ticket_closed",
    }
)


def trace_key(trace_id: str) -> str:
    """Return the store key for a Trace event list."""
    return f"{TRACE_KEY_PREFIX}{trace_id}"


def make_event(
    *,
    at: str,
    type: str,
    trace_id: str,
    actor: str,
    message_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    detail: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build one TraceEvent. ``type`` must be a known event type."""
    if type not in EVENT_TYPES:
        raise ValueError(f"unknown trace event type {type!r}")
    event: dict[str, Any] = {
        "at": at,
        "type": type,
        "trace_id": trace_id,
        "actor": actor,
        "detail": dict(detail) if detail is not None else {},
    }
    if message_id is not None:
        event["message_id"] = message_id
    if ticket_id is not None:
        event["ticket_id"] = ticket_id
    return event


async def append_event(store: Store, event: Mapping[str, Any]) -> dict[str, Any]:
    """Append ``event`` to its Trace, dropping the oldest past the cap."""
    stored = dict(event)
    trace_id = str(stored["trace_id"])
    key = trace_key(trace_id)
    existing = await store.get(key)
    events: list[dict[str, Any]]
    if isinstance(existing, list):
        events = list(existing)
    else:
        events = []
    events.append(stored)
    if len(events) > MAX_TRACE_EVENTS:
        events = events[-MAX_TRACE_EVENTS:]
    await store.put(key, events)
    await store.set_add(TRACES_SET, trace_id)
    return stored


async def load_events(store: Store, trace_id: str) -> list[dict[str, Any]]:
    """Return stored events for ``trace_id``, oldest first, or empty."""
    record = await store.get(trace_key(trace_id))
    if not isinstance(record, list):
        return []
    return [dict(item) for item in record if isinstance(item, dict)]


def caller_appears(events: list[Mapping[str, Any]], address: str) -> bool:
    """Return True when ``address`` is an actor, sender, or recipient."""
    for event in events:
        if event.get("actor") == address:
            return True
        detail = event.get("detail")
        if isinstance(detail, Mapping):
            if detail.get("sender") == address or detail.get("recipient") == address:
                return True
    return False
