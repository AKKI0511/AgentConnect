"""Collect a Ticket without treating ``open`` as success.

``collect="wait"`` returns when the work is terminal or when the
Runtime wait hold ends. That wait is not the work deadline. Keep
calling ``get_result`` until a terminal state or the Ticket deadline.
This helper is local to the recipes. It is not a public SDK API.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from agentconnect import BaseAgent, Ticket


def work_deadline(ticket: Ticket) -> datetime:
    """Return the Ticket's work cutoff as UTC."""
    return datetime.fromisoformat(ticket.deadline.replace("Z", "+00:00"))


async def until_terminal(
    agent: BaseAgent,
    ticket: Ticket,
    *,
    poll_seconds: float = 0.05,
    stop_after_seconds: float | None = None,
) -> Ticket:
    """Poll ``get_result`` until ``ticket`` leaves ``open``.

    Stops at the work deadline. ``stop_after_seconds`` is an optional
    caller abort. It does not end accepted work, and an embedded Team
    that then ``stop()``s destroys that in-memory Runtime.
    """
    current = ticket
    started = asyncio.get_running_loop().time()
    while current.state == "open":
        now_mono = asyncio.get_running_loop().time()
        if stop_after_seconds is not None and now_mono - started >= stop_after_seconds:
            return current
        if datetime.now(timezone.utc) >= work_deadline(current):
            current = await agent.get_result(current.id)
            for _ in range(20):
                if current.state != "open":
                    return current
                await asyncio.sleep(poll_seconds)
                current = await agent.get_result(current.id)
            return current
        await asyncio.sleep(poll_seconds)
        current = await agent.get_result(current.id)
    return current


def show_ticket(ticket: Ticket, *, label: str = "ticket") -> None:
    """Print state and payload. Never prints success for non-completed work."""
    print(f"{label} state: {ticket.state}")
    if ticket.state == "completed":
        print(f"{label} response: {ticket.response.content}")
        return
    if ticket.state == "failed":
        print(f"{label} error: {ticket.error.message}")
        return
    if ticket.state == "declined":
        print(f"{label} declined")
        return
    if ticket.state == "expired":
        print(f"{label} expired")
        return
    print(f"{label} still open; id={ticket.id}")
