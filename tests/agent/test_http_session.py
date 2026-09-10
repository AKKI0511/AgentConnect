"""HTTP Session: join by URL, same handler code, reconnect after restart."""

from __future__ import annotations

import asyncio
import socket

import pytest

from agentconnect.agent import BaseAgent, SessionError
from agentconnect.team import Team
from tests.agent.conftest import DeferredAgent, EchoAgent


def _free_loopback_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


@pytest.mark.asyncio
async def test_join_by_url_same_as_embedded():
    team = await Team("content-squad", session_ttl_seconds=30).start()
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve()
        await writer.join(url)
        await researcher.join(url)
        result = await researcher.ask("writer", "via-http", deadline_seconds=8)
        assert result.state == "completed"
        assert result.content == {"echo": "via-http"}
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_join_retries_until_http_team_is_up():
    port = _free_loopback_port()
    url = f"http://127.0.0.1:{port}"
    writer = EchoAgent(name="writer")
    task = asyncio.create_task(writer.join(url))
    await asyncio.sleep(0.2)
    assert not task.done()
    team = await Team("content-squad", session_ttl_seconds=30).start()
    try:
        await team.serve(port=port)
        await asyncio.wait_for(task, timeout=8)
        assert writer.connected
        assert writer.address == "writer@content-squad"
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_reconnects_after_team_restart():
    port = _free_loopback_port()
    team = await Team("content-squad", session_ttl_seconds=15).start()
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve(port=port)
        await writer.join(url)
        await researcher.join(url)
        first = await researcher.ask("writer", "before", deadline_seconds=8)
        assert first.state == "completed"
        await team.stop()

        team = await Team("content-squad", session_ttl_seconds=15).start()
        await team.serve(port=port)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 8

        async def _until_live(agent: EchoAgent) -> None:
            while loop.time() < deadline:
                try:
                    await agent.find("draft")
                    return
                except Exception:
                    await asyncio.sleep(0.15)
            raise AssertionError(f"{agent.name} did not reconnect")

        await asyncio.gather(_until_live(writer), _until_live(researcher))
        second = await researcher.ask("writer", "after", deadline_seconds=8)
        assert second.state == "completed"
        assert second.content == {"echo": "after"}
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_serve_rejects_non_loopback():
    team = await Team("content-squad").start()
    try:
        with pytest.raises(Exception) as exc:
            await team.serve(host="0.0.0.0", port=0)
        assert getattr(exc.value, "code", None) == "invalid_request"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_busy_mailbox_does_not_replace_http_transport():
    team = await Team(
        "content-squad",
        max_mailbox_depth=1,
        session_ttl_seconds=30,
    ).start()
    writer = DeferredAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve()
        await writer.join(url)
        await researcher.join(url)
        transport = researcher._session._transport
        pending = await researcher.ask(
            "writer", "one", deadline_seconds=8, collect="ticket"
        )
        assert pending.state == "open"
        with pytest.raises(SessionError) as exc:
            await researcher.ask("writer", "two", deadline_seconds=8, collect="ticket")
        assert exc.value.code == "busy"
        assert researcher._session._transport is transport
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()


async def _until_terminal(agent, ticket_id, *, timeout=8.0):
    loop = asyncio.get_running_loop()
    limit = loop.time() + timeout
    ticket = await agent.get_result(ticket_id)
    while ticket.state == "open" and loop.time() < limit:
        await asyncio.sleep(0.05)
        ticket = await agent.get_result(ticket_id)
    return ticket


@pytest.mark.asyncio
async def test_http_long_running_wait_returns_open_then_completes():
    team = await Team(
        "content-squad",
        wait_hold_seconds=0.15,
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class AgentC(EchoAgent):
        async def handle(self, message, ctx):
            await asyncio.sleep(0.9)
            return {"from": "c"}

    class AgentB(BaseAgent):
        async def handle(self, message, ctx):
            handle = ctx.defer()
            inner = await ctx.ask("agent-c", "go", collect="wait")
            while inner.state == "open":
                await asyncio.sleep(0.05)
                inner = await self.get_result(inner.id)
            if inner.state == "completed":
                await handle.reply(inner.content)
            return None

    agent_c = AgentC(name="agent-c")
    agent_b = AgentB(name="agent-b")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve()
        await agent_c.join(url)
        await agent_b.join(url)
        await researcher.join(url)
        pending = await researcher.ask(
            "agent-b", "start", deadline_seconds=8, collect="wait"
        )
        assert pending.state == "open"
        ticket = await _until_terminal(researcher, pending.id, timeout=8)
        assert ticket.state == "completed"
        assert ticket.content == {"from": "c"}
        assert ticket.id == pending.id
    finally:
        await researcher.leave()
        await agent_b.leave()
        await agent_c.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_http_hard_expiry_returns_expired_ticket():
    team = await Team(
        "content-squad",
        wait_hold_seconds=0.15,
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class Slow(BaseAgent):
        async def handle(self, message, ctx):
            await asyncio.sleep(2)
            return {"late": True}

    writer = Slow(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve()
        await writer.join(url)
        await researcher.join(url)
        pending = await researcher.ask(
            "writer", "hold", deadline_seconds=0.4, collect="wait"
        )
        assert pending.state in {"open", "expired"}
        ticket = await _until_terminal(researcher, pending.id, timeout=5)
        assert ticket.state == "expired"
        assert ticket.id == pending.id
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
