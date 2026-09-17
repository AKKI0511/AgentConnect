"""Correctness without process-local work hints."""

from __future__ import annotations

import asyncio

import pytest
from tests.agent.conftest import EchoAgent
from tests.m8.budgets import WAIT_AMPLIFICATION_HINTS_S, WAIT_WITHOUT_HINTS_S
from tests.m8.stores import open_m8_store
from tests.m8.support import start_team

from agentconnect.team.store.memory import MemoryStore

pytestmark = pytest.mark.asyncio

_STORE_KINDS = [
    "yielding-memory",
    pytest.param("redis", marks=pytest.mark.redis),
]


def _silence_hints(team) -> None:
    team._signal_work = lambda membership_name: None  # type: ignore[method-assign]
    team._notify = lambda ticket_id: None  # type: ignore[method-assign]


@pytest.mark.parametrize("store_kind", _STORE_KINDS)
@pytest.mark.parametrize("via_http", [False, True], ids=["embedded", "http"])
async def test_completes_without_process_local_hints(store_kind: str, via_http: bool):
    store = await open_m8_store(store_kind)
    team = await start_team(store, lease_ttl_seconds=8, wait_hold_seconds=0.3)
    _silence_hints(team)
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        target = await team.serve() if via_http else team
        await writer.join(target)
        await researcher.join(target)
        started = asyncio.get_running_loop().time()
        pending = await researcher.ask(
            "writer", "no-hint", deadline_seconds=8, collect="ticket"
        )
        ticket = pending
        deadline_at = started + WAIT_WITHOUT_HINTS_S
        while (
            ticket.state == "open" and asyncio.get_running_loop().time() < deadline_at
        ):
            await asyncio.sleep(0.05)
            ticket = await researcher.get_result(pending.id)
        elapsed = asyncio.get_running_loop().time() - started
        assert ticket.state == "completed"
        assert ticket.content == {"echo": "no-hint"}
        assert elapsed < WAIT_WITHOUT_HINTS_S
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
        await store.clear()
        await store.close()


async def test_wait_with_hints_does_not_amplify_short_work():
    store = MemoryStore()
    team = await start_team(store, lease_ttl_seconds=8, wait_hold_seconds=2.0)
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        started = asyncio.get_running_loop().time()
        ticket = await researcher.ask(
            "writer", "fast", deadline_seconds=8, collect="wait"
        )
        elapsed = asyncio.get_running_loop().time() - started
        assert ticket.state == "completed"
        assert elapsed < WAIT_AMPLIFICATION_HINTS_S
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
