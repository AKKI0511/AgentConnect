"""Trace timeline stored by the Team Runtime.

A Trace is one causal operation. ``get_trace`` returns the events the
Runtime recorded for a ``trace_id``. The operator receives the full
list. A member receives only events that name that Membership.

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
    parent_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    detail: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build one TraceEvent. ``type`` must be a known event type.

    ``parent_id`` is the parent of ``message_id`` when that Message has
    one. Omit it on a root Message.
    """
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
    if parent_id is not None:
        event["parent_id"] = parent_id
    if ticket_id is not None:
        event["ticket_id"] = ticket_id
    return event


def parent_id_of(message: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Return ``message['parent_id']`` when present."""
    if not isinstance(message, Mapping):
        return None
    parent = message.get("parent_id")
    return str(parent) if parent else None


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


def event_names_member(
    event: Mapping[str, Any],
    address: str,
    messages: Mapping[str, Mapping[str, Any]],
) -> bool:
    """Return True when ``event`` names ``address``.

    Named means the event ``actor``, a ``sender`` or ``recipient`` in
    ``detail``, or the sender or recipient of the Message ``message_id``.
    """
    if event.get("actor") == address:
        return True
    detail = event.get("detail")
    if isinstance(detail, Mapping):
        if detail.get("sender") == address or detail.get("recipient") == address:
            return True
    message_id = event.get("message_id")
    message = messages.get(message_id) if isinstance(message_id, str) else None
    if isinstance(message, Mapping):
        if address in {message.get("sender"), message.get("recipient")}:
            return True
    return False


async def visible_events(
    store: Store, events: list[Mapping[str, Any]], address: str
) -> list[dict[str, Any]]:
    """Return the subset of ``events`` that name ``address``, in order."""
    ids = {
        str(event["message_id"])
        for event in events
        if isinstance(event.get("message_id"), str)
    }
    messages: dict[str, dict[str, Any]] = {}
    for message_id in ids:
        record = await store.get(f"msg:{message_id}")
        if isinstance(record, dict):
            messages[message_id] = record
    return [
        dict(event) for event in events if event_names_member(event, address, messages)
    ]
