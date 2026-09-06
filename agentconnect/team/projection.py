"""Project stored Runtime records onto public result shapes.

Internal Membership ids stay on stored records. Public results omit them
at known record boundaries. Agent-controlled JSON (``content``,
``metadata``, ``error``, and nested objects inside those) is copied as-is.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MESSAGE_INTERNAL = ("sender_membership_id", "recipient_membership_id")
_TICKET_INTERNAL = ("requester_membership_id", "recipient_membership_id")
_EVENT_INTERNAL = ("actor_membership_id",)


def _omit(record: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in keys}


def public_message(message: Mapping[str, Any]) -> dict[str, Any]:
    """Public Message. Nested Agent JSON is not rewritten."""
    return _omit(message, _MESSAGE_INTERNAL)


def public_ticket(ticket: Mapping[str, Any]) -> dict[str, Any]:
    """Public Ticket. A nested response Message is projected the same way."""
    out = _omit(ticket, _TICKET_INTERNAL)
    response = out.get("response")
    if isinstance(response, dict):
        out["response"] = public_message(response)
    return out


def public_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Public TraceEvent."""
    return _omit(event, _EVENT_INTERNAL)


def public_send_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Send result: Message and optional Ticket."""
    out = dict(result)
    if isinstance(out.get("message"), dict):
        out["message"] = public_message(out["message"])
    if isinstance(out.get("ticket"), dict):
        out["ticket"] = public_ticket(out["ticket"])
    return out


def public_lease_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Lease result: each Delivery Message and history window."""
    deliveries: list[dict[str, Any]] = []
    for item in result.get("deliveries") or []:
        if not isinstance(item, dict):
            continue
        delivery = dict(item)
        if isinstance(delivery.get("message"), dict):
            delivery["message"] = public_message(delivery["message"])
        history = delivery.get("history")
        if isinstance(history, list):
            delivery["history"] = [
                public_message(entry) if isinstance(entry, dict) else entry
                for entry in history
            ]
        deliveries.append(delivery)
    return {"deliveries": deliveries}


def public_ticket_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Reply or complete result: optional Ticket."""
    out = dict(result)
    if isinstance(out.get("ticket"), dict):
        out["ticket"] = public_ticket(out["ticket"])
    return out


def public_history_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """History page: retained Messages."""
    out = dict(result)
    messages = out.get("messages")
    if isinstance(messages, list):
        out["messages"] = [
            public_message(item) if isinstance(item, dict) else item
            for item in messages
        ]
    return out


def public_trace_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Trace result: events visible to the caller."""
    out = dict(result)
    events = out.get("events")
    if isinstance(events, list):
        out["events"] = [
            public_event(item) if isinstance(item, dict) else item for item in events
        ]
    return out
