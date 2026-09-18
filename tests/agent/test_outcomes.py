"""Typed Agent terminal outcomes on embedded and HTTP Sessions."""

from __future__ import annotations

import asyncio

import pytest
from tests.agent.conftest import BoomAgent, DeclineAgent, DeferredAgent, EchoAgent
from tests.support.stores import open_store
from tests.support.runtime import start_team

from agentconnect.agent import BaseAgent, Context
from agentconnect.core.base import JsonValue
from agentconnect.core.message import MailboxMessage
from agentconnect.team import Team

pytestmark = pytest.mark.asyncio

_STORE_KINDS = [
    "yielding-memory",
    pytest.param("redis", marks=pytest.mark.redis),
]


class NullContentAgent(BaseAgent):
    """Completes a request with JSON null content."""

    async def handle(self, message: MailboxMessage, ctx: Context) -> JsonValue | None:
        if message.kind == "request":
            pending = ctx.defer()
            await pending.reply(None)
            return None
        return None


async def _join_pair(
    team: Team, writer: BaseAgent, researcher: BaseAgent, via_http: bool
):
    target: Team | str = team
    if via_http:
        target = await team.serve()
    await writer.join(target)
    await researcher.join(target)
    return target


@pytest.mark.parametrize(
    "store_kind",
    [
        "yielding-memory",
        pytest.param("redis", marks=pytest.mark.redis),
    ],
)
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
async def test_completed_echo(store_kind: str, via_http: bool):
    store = await open_store(store_kind)
    team = await start_team(store, lease_ttl_seconds=8)
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        await _join_pair(team, writer, researcher, via_http)
        ticket = await researcher.ask("writer", "ping", deadline_seconds=8)
        assert ticket.state == "completed"
        assert ticket.content == {"echo": "ping"}
        polled = await researcher.get_result(ticket.id)
        assert polled.state == "completed"
        assert polled.response.content == ticket.response.content
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
        await store.clear()
        await store.close()


@pytest.mark.parametrize("store_kind", _STORE_KINDS)
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
async def test_completed_null_content(store_kind: str, via_http: bool):
    store = await open_store(store_kind)
    team = await start_team(store, lease_ttl_seconds=8)
    writer = NullContentAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        await _join_pair(team, writer, researcher, via_http)
        ticket = await researcher.ask("writer", "empty", deadline_seconds=8)
        assert ticket.state == "completed"
        assert ticket.response.content is None
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
        await store.clear()
        await store.close()


@pytest.mark.parametrize("store_kind", _STORE_KINDS)
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
async def test_declined(store_kind: str, via_http: bool):
    store = await open_store(store_kind)
    team = await start_team(store, lease_ttl_seconds=8)
    writer = DeclineAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        await _join_pair(team, writer, researcher, via_http)
        ticket = await researcher.ask("writer", "no", deadline_seconds=8)
        assert ticket.state == "declined"
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
        await store.clear()
        await store.close()


@pytest.mark.parametrize("store_kind", _STORE_KINDS)
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
async def test_failed(store_kind: str, via_http: bool):
    store = await open_store(store_kind)
    team = await start_team(store, lease_ttl_seconds=8)
    writer = BoomAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        await _join_pair(team, writer, researcher, via_http)
        ticket = await researcher.ask("writer", "boom", deadline_seconds=8)
        assert ticket.state == "failed"
        assert ticket.error.message == "The handler failed."
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
        await store.clear()
        await store.close()


@pytest.mark.parametrize("store_kind", _STORE_KINDS)
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
async def test_expired_deadline(store_kind: str, via_http: bool):
    store = await open_store(store_kind)
    team = await start_team(
        store, lease_ttl_seconds=8, sweep_interval_seconds=0.05, wait_hold_seconds=0.2
    )
    writer = DeferredAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        await _join_pair(team, writer, researcher, via_http)
        ticket = await researcher.ask(
            "writer", "slow", deadline_seconds=0.4, collect="ticket"
        )
        deadline_at = asyncio.get_running_loop().time() + 3.0
        while (
            ticket.state == "open" and asyncio.get_running_loop().time() < deadline_at
        ):
            await asyncio.sleep(0.05)
            ticket = await researcher.get_result(ticket.id)
        assert ticket.state == "expired"
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
        await store.clear()
        await store.close()
