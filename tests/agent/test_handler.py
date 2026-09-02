"""Handler output forms: reply, decline, fail, and take a ticket."""

from __future__ import annotations

import asyncio

import pytest

from agentconnect.team import Team
from tests.agent.conftest import BoomAgent, DeclineAgent, DeferredAgent, EchoAgent


@pytest.mark.asyncio
async def test_return_value_completes_ticket(team: Team):
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        result = await researcher.ask(
            "writer", {"task": "draft"}, deadline_seconds=5, collect="wait"
        )
        assert result["status"] == "ticketed"
        assert result["ticket"]["state"] == "completed"
        assert result["ticket"]["response"]["content"] == {"echo": {"task": "draft"}}
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
        result = await researcher.ask("writer", "please", deadline_seconds=5)
        assert result["ticket"]["state"] == "declined"
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
        result = await researcher.ask("writer", "please", deadline_seconds=5)
        assert result["ticket"]["state"] == "failed"
        assert result["ticket"]["error"]["code"] == "handler_failed"
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
        assert pending["ticket"]["state"] == "open"
        for _ in range(50):
            if writer.handle is not None:
                break
            await asyncio.sleep(0.05)
        assert writer.handle is not None
        await writer.handle.reply("done later")
        ticket = await researcher.get_result(pending["ticket"]["id"])
        assert ticket["state"] == "completed"
        assert ticket["response"]["content"] == "done later"
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
        assert sent["status"] == "accepted"
        assert "ticket" not in sent
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_ctx_ask_mid_handling(team: Team):
    class Relay(EchoAgent):
        async def process_message(self, message, ctx):
            if message.content == "relay":
                inner = await ctx.ask(
                    "writer", "from-relay", deadline_seconds=5, collect="wait"
                )
                return inner["ticket"]["response"]["content"]
            return await super().process_message(message, ctx)

    writer = EchoAgent(name="writer")
    relay = Relay(name="relay")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await relay.join(team)
    await researcher.join(team)
    try:
        result = await researcher.ask("relay", "relay", deadline_seconds=8)
        assert result["ticket"]["state"] == "completed"
        assert result["ticket"]["response"]["content"] == {"echo": "from-relay"}
    finally:
        await writer.leave()
        await relay.leave()
        await researcher.leave()
