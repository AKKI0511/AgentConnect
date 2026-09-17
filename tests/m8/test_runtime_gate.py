"""Runtime wait, expiry, and retained-storage gates."""

from __future__ import annotations

import asyncio
import time
import tracemalloc

import pytest
from tests.m8.budgets import WAIT_AMPLIFICATION_HINTS_S, percentile
from tests.m8.support import message_id, start_team
from tests.team.conftest import deadline, join_member

from agentconnect.team.retention import RETAINED_BYTES_KEY
from agentconnect.team.store.memory import MemoryStore

pytestmark = pytest.mark.asyncio


async def test_send_lease_reply_latency_on_yielding_store():
    from tests.m8.stores import YieldingStore

    store = YieldingStore()
    team = await start_team(store, lease_ttl_seconds=8)
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        samples: list[float] = []
        for _ in range(10):
            started = time.perf_counter()
            sent = await team.send(
                researcher["session_token"],
                {
                    "id": message_id(),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "ping",
                    "collect": "ticket",
                    "deadline": deadline(10),
                },
            )
            delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
            await team.reply(
                writer["session_token"],
                {
                    "id": message_id(),
                    "lease_id": delivery["lease_id"],
                    "outcome": "completed",
                    "content": "pong",
                },
            )
            done = await team.get_result(
                researcher["session_token"], sent["message"]["id"]
            )
            samples.append(time.perf_counter() - started)
            assert done["state"] == "completed"
        assert percentile(samples, 95) < WAIT_AMPLIFICATION_HINTS_S
    finally:
        await team.stop()


async def test_expiry_does_not_block_unrelated_send():
    store = MemoryStore()
    team = await start_team(store, sweep_interval_seconds=0.05, lease_ttl_seconds=8)
    try:
        writer = await join_member(team, "writer", max_in_flight=4)
        researcher = await join_member(team, "researcher")
        await team.send(
            researcher["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "request",
                "content": "expire-me",
                "collect": "ticket",
                "deadline": deadline(0.2),
            },
        )
        started = time.perf_counter()
        sent = await team.send(
            researcher["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "event",
                "content": "other",
            },
        )
        elapsed = time.perf_counter() - started
        assert elapsed < 0.1
        assert sent["status"] == "accepted"
        await asyncio.sleep(0.4)
        leased = await team.lease(writer["session_token"], max_items=10)
        kinds = [item["message"]["kind"] for item in leased["deliveries"]]
        assert "event" in kinds
    finally:
        await team.stop()


async def test_find_allocation_returns_after_warm_searches():
    store = MemoryStore()
    team = await start_team(store)
    try:
        for index in range(40):
            name = f"agent{index:02d}"
            from tests.m8.support import short_profile
            from tests.team.conftest import make_did

            await join_member(
                team, name, agent_did=make_did(name), profile=short_profile(index)
            )
        caller = await join_member(team, "researcher")
        tracemalloc.start()
        baseline = tracemalloc.get_traced_memory()[0]
        for _ in range(8):
            found = await team.find(caller["session_token"], "similar paperwork")
            assert found["matches"]
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        # Peak may exceed baseline; live traced bytes should not grow without bound.
        assert current < baseline + 8_000_000
        assert peak < 32_000_000
        retained = await store.get(RETAINED_BYTES_KEY)
        assert retained is None or int(retained) >= 0
    finally:
        await team.stop()
