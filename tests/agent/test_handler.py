"""Handler output forms: reply, decline, fail, and take a ticket."""

from __future__ import annotations

import asyncio

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.team import Team
from tests.agent.conftest import BoomAgent, DeclineAgent, DeferredAgent, EchoAgent


@pytest.mark.asyncio
async def test_return_value_completes_ticket(team: Team):
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask(
            "writer", {"task": "draft"}, deadline_seconds=5, collect="wait"
        )
        assert ticket.state == "completed"
        assert ticket.content == {"echo": {"task": "draft"}}
        assert ticket.trace_id
        polled = await researcher.get_result(ticket.id)
        assert polled.content == ticket.content
        assert polled.trace_id is None
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_return_none_declines_request(team: Team):
    writer = DeclineAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask("writer", "please", deadline_seconds=5)
        assert ticket.state == "declined"
        assert ticket.content is None
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_raise_fails_request(team: Team):
    writer = BoomAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask("writer", "please", deadline_seconds=5)
        assert ticket.state == "failed"
        assert ticket.error.code == "handler_failed"
        assert ticket.content is None
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_ticket_handle_replies_later(team: Team):
    writer = DeferredAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        pending = await researcher.ask(
            "writer",
            "later",
            deadline_seconds=8,
            collect="ticket",
        )
        assert pending.state == "open"
        for _ in range(50):
            if writer.ticket_handle is not None:
                break
            await asyncio.sleep(0.05)
        assert writer.ticket_handle is not None
        await writer.ticket_handle.reply("done later")
        ticket = await researcher.get_result(pending.id)
        assert ticket.state == "completed"
        assert ticket.content == "done later"
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_event_does_not_open_ticket(team: Team):
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        sent = await researcher.tell("writer", {"note": "fyi"})
        assert sent.status == "accepted"
        assert "ticket" not in sent
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_ctx_ask_mid_handling(team: Team):
    class Relay(EchoAgent):
        async def handle(self, message, ctx):
            if message.content == "relay":
                inner = await ctx.ask(
                    "writer", "from-relay", deadline_seconds=5, collect="wait"
                )
                return inner.content
            return await super().handle(message, ctx)

    writer = EchoAgent(name="writer")
    relay = Relay(name="relay")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await relay.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask("relay", "relay", deadline_seconds=8)
        assert ticket.state == "completed"
        assert ticket.content == {"echo": "from-relay"}
    finally:
        await writer.leave()
        await relay.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_ctx_sender_is_the_requester_address(team: Team):
    class Who(EchoAgent):
        async def handle(self, message, ctx):
            return {"sender": ctx.sender, "did": ctx.sender_did}

    writer = Who(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask("writer", "who", deadline_seconds=5)
        assert ticket.content["sender"] == researcher.address
        assert ticket.content["did"] == researcher.agent_did
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_process_message_override_still_runs(team: Team):
    class Legacy(BaseAgent):
        async def process_message(self, message, ctx):
            return {"legacy": message.content}

    writer = Legacy(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask("writer", "hi", deadline_seconds=5)
        assert ticket.content == {"legacy": "hi"}
    finally:
        await writer.leave()
        await researcher.leave()


def test_unknown_constructor_kwargs_fail():
    with pytest.raises(TypeError):
        EchoAgent(name="writer", enable_payments=True)
    with pytest.raises(TypeError):
        EchoAgent(name="writer", agent_id="writer")
