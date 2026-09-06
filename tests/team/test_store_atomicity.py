"""Insert-if-absent and compare-and-set on the Memory Store."""

from __future__ import annotations

import asyncio

import pytest

from agentconnect.team.store import MemoryStore, StoreRecord
from agentconnect.team.store.ops import Cas, Insert


@pytest.mark.asyncio
async def test_insert_wins_once_under_contention():
    store = MemoryStore()
    await store.open()
    results = await asyncio.gather(*[store.insert("k", {"n": i}) for i in range(20)])
    assert sum(1 for ok in results if ok) == 1
    assert await store.get("k") == {"n": results.index(True)}


@pytest.mark.asyncio
async def test_compare_and_set_rejects_stale_version():
    store = MemoryStore()
    await store.open()
    assert await store.insert("ticket:1", {"state": "open"})
    record = await store.get_record("ticket:1")
    assert isinstance(record, StoreRecord)
    assert record.version == 1
    first = await store.compare_and_set("ticket:1", 1, {"state": "completed"})
    second = await store.compare_and_set("ticket:1", 1, {"state": "failed"})
    assert first is True
    assert second is False
    updated = await store.get_record("ticket:1")
    assert updated is not None
    assert updated.value["state"] == "completed"
    assert updated.version == 2


@pytest.mark.asyncio
async def test_index_add_if_card_below_is_exact():
    store = MemoryStore()
    await store.open()
    results = await asyncio.gather(
        *[store.index_add_if_card_below("idx", float(i), f"m{i}", 3) for i in range(12)]
    )
    assert sum(1 for ok in results if ok) == 3
    assert await store.index_card("idx") == 3


@pytest.mark.asyncio
async def test_increment_if_below_caps_at_limit():
    store = MemoryStore()
    await store.open()
    results = await asyncio.gather(
        *[store.increment_if_below("held", 2) for _ in range(10)]
    )
    assert sum(1 for ok in results if ok) == 2
    assert await store.get("held") == 2
    assert await store.decrement_floor("held") == 1
    assert await store.decrement_floor("held") == 0
    assert await store.decrement_floor("held") == 0


@pytest.mark.asyncio
async def test_concurrent_put_assigns_distinct_versions():
    store = MemoryStore()
    await store.open()
    assert await store.insert("k", {"n": 0})
    await asyncio.gather(*[store.put("k", {"n": i}) for i in range(10)])
    record = await store.get_record("k")
    assert record is not None
    assert record.version == 11


@pytest.mark.asyncio
async def test_apply_is_all_or_nothing():
    store = MemoryStore()
    await store.open()
    assert await store.insert("ticket", {"state": "open"})
    record = await store.get_record("ticket")
    assert record is not None
    result = await store.apply(
        [
            Insert("msg", {"id": "m1"}),
            Cas("ticket", record.version + 3, {"state": "completed"}),
        ]
    )
    assert result.ok is False
    assert await store.get("msg") is None
    assert await store.get("ticket") == {"state": "open"}
