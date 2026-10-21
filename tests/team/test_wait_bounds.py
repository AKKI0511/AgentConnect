"""Expiry must not stall unrelated send or hide a still-leasable event."""

from __future__ import annotations

import asyncio
import time

import pytest
from tests.support.runtime import message_id, start_team
from tests.team.conftest import deadline, join_member

from agentconnect.team.store.memory import MemoryStore

pytestmark = pytest.mark.asyncio


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
