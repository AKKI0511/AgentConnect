"""Mailbox pull port: per-item documents behind a time-ordered index."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from agentconnect.team import mailbox as mailbox_mod
from agentconnect.team.codec import format_timestamp
from agentconnect.team.store import MemoryStore


def _now() -> tuple[datetime, str]:
    instant = datetime.now(timezone.utc)
    return instant, format_timestamp(instant)


@pytest.mark.asyncio
async def test_enqueue_stops_at_exact_depth():
    store = MemoryStore()
    await store.open()
    now, now_ts = _now()
    address = "writer@content-squad"
    first = await mailbox_mod.enqueue(store, address, "a", now_ts, max_depth=2)
    second = await mailbox_mod.enqueue(store, address, "b", now_ts, max_depth=2)
    third = await mailbox_mod.enqueue(store, address, "c", now_ts, max_depth=2)
    assert first == "ok"
    assert second == "ok"
    assert third == "busy"
    assert await mailbox_mod.depth(store, address) == 2
    assert (
        await mailbox_mod.enqueue(store, address, "a", now_ts, max_depth=2)
        == "duplicate"
    )


@pytest.mark.asyncio
async def test_concurrent_enqueue_respects_depth_cap():
    store = MemoryStore()
    await store.open()
    _, now_ts = _now()
    address = "writer@content-squad"
    results = await asyncio.gather(
        *[
            mailbox_mod.enqueue(store, address, f"m{i}", now_ts, max_depth=2)
            for i in range(8)
        ]
    )
    assert results.count("ok") == 2
    assert results.count("busy") == 6
    assert await mailbox_mod.depth(store, address) == 2


@pytest.mark.asyncio
async def test_two_claims_only_one_wins():
    store = MemoryStore()
    await store.open()
    now, now_ts = _now()
    address = "writer@content-squad"
    assert (
        await mailbox_mod.enqueue(store, address, "msg-1", now_ts, max_depth=4) == "ok"
    )
    expires = format_timestamp(now + timedelta(seconds=30))
    first, second = await asyncio.gather(
        mailbox_mod.claim(store, address, "msg-1", "lease-a", expires, now, now_ts),
        mailbox_mod.claim(store, address, "msg-1", "lease-b", expires, now, now_ts),
    )
    winners = [item for item in (first, second) if item is not None]
    assert len(winners) == 1
    assert winners[0]["state"] == "leased"
    assert winners[0]["attempt"] == 1
    assert await mailbox_mod.depth(store, address) == 1


@pytest.mark.asyncio
async def test_acknowledge_drops_depth_return_makes_ready():
    store = MemoryStore()
    await store.open()
    now, now_ts = _now()
    address = "writer@content-squad"
    await mailbox_mod.enqueue(store, address, "msg-1", now_ts, max_depth=4)
    expires = format_timestamp(now + timedelta(seconds=30))
    claimed = await mailbox_mod.claim(
        store, address, "msg-1", "lease-a", expires, now, now_ts
    )
    assert claimed is not None
    assert await mailbox_mod.ready_ids(store, address, now, limit=4) == []
    returned_at = format_timestamp(now)
    assert await mailbox_mod.return_item(
        store, address, "msg-1", "lease-a", returned_at
    )
    assert await mailbox_mod.ready_ids(store, address, now, limit=4) == ["msg-1"]
    claimed_again = await mailbox_mod.claim(
        store, address, "msg-1", "lease-b", expires, now, now_ts
    )
    assert claimed_again is not None
    assert claimed_again["attempt"] == 2
    assert await mailbox_mod.acknowledge(store, address, "msg-1", "lease-b")
    assert await mailbox_mod.depth(store, address) == 0
