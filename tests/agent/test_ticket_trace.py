"""Ticket.trace_id is Runtime-retained across Session replacement."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.team import Team
from tests.agent.conftest import BoomAgent, DeclineAgent, DeferredAgent, EchoAgent

_RECIPIENTS = {
    "open": DeferredAgent,
    "completed": EchoAgent,
    "failed": BoomAgent,
    "declined": DeclineAgent,
    "expired": DeferredAgent,
}


async def _until_terminal(agent: BaseAgent, ticket_id: str, *, timeout: float = 8.0):
    loop = asyncio.get_running_loop()
    limit = loop.time() + timeout
    ticket = await agent.get_result(ticket_id)
    while ticket.state == "open" and loop.time() < limit:
        await asyncio.sleep(0.05)
        ticket = await agent.get_result(ticket_id)
    return ticket


@pytest.mark.asyncio
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
@pytest.mark.parametrize(
    "outcome",
    ["open", "completed", "failed", "declined", "expired"],
)
async def test_ticket_trace_id_survives_new_session(via_http: bool, outcome: str):
    kwargs: dict = {
        "session_ttl_seconds": 30,
        "lease_ttl_seconds": 10,
        "sweep_interval_seconds": 0.05,
    }
    if outcome == "expired":
        kwargs.update(wait_hold_seconds=0.15, lease_ttl_seconds=0.2)
    team = await Team("content-squad", **kwargs).start()
    writer = _RECIPIENTS[outcome](name="writer")
    first = EchoAgent(name="researcher")
    second: EchoAgent | None = None
    try:
        target = await team.serve() if via_http else team
        await writer.join(target)
        await first.join(target)
        ask_kw: dict = {"deadline_seconds": 0.4 if outcome == "expired" else 8}
        if outcome == "open":
            ask_kw["collect"] = "ticket"
        ticket = await first.ask("writer", outcome, **ask_kw)
        if outcome == "open":
            ticket = await first.get_result(ticket.id)
            assert ticket.state == "open"
        else:
            if ticket.state == "open":
                ticket = await _until_terminal(first, ticket.id)
            assert ticket.state == outcome
        trace_id = str(uuid.UUID(ticket.trace_id))
        ticket_id = ticket.id
        identity = first.identity
        await first.leave()
        second = EchoAgent(name="researcher", identity=identity)
        await second.join(target)
        polled = await second.get_result(ticket_id)
        assert polled.state == ticket.state
        assert str(uuid.UUID(polled.trace_id)) == trace_id
    finally:
        if second is not None:
            await second.leave()
        await first.leave()
        await writer.leave()
        await team.stop()
