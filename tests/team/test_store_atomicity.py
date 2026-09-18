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


@pytest.mark.asyncio
async def test_index_range_skips_unrelated_future_members():
    store = MemoryStore()
    await store.open()
    for index in range(4000):
        await store.index_add("idx", 1_000_000.0 + index, f"future-{index}")
    await store.index_add("idx", 1.0, "due-a")
    await store.index_add("idx", 2.0, "due-b")
    due = await store.index_range("idx", max_score=10.0)
    assert due == ["due-a", "due-b"]
    page = await store.index_range("idx", max_score=1_000_000.0 + 5000, limit=2)
    assert page == ["due-a", "due-b"]


@pytest.mark.asyncio
async def test_mixed_list_write_is_isolated_from_caller_mutation():
    store = MemoryStore()
    await store.open()
    payload = [1, {"status": "accepted"}]
    await store.put("doc", payload)
    payload[1]["status"] = "spoofed"
    payload.append({"extra": True})
    stored = await store.get("doc")
    assert stored == [1, {"status": "accepted"}]
    record = await store.get_record("doc")
    assert record is not None
    assert record.version == 1


@pytest.mark.asyncio
async def test_mixed_list_read_is_isolated_from_caller_mutation():
    store = MemoryStore()
    await store.open()
    await store.put("doc", [1, {"status": "accepted"}])
    loaded = await store.get("doc")
    assert loaded is not None
    loaded[1]["status"] = "spoofed"
    loaded.append(2)
    again = await store.get("doc")
    assert again == [1, {"status": "accepted"}]
    many = await store.get_many(["doc"])
    many[0][1]["status"] = "other"
    assert await store.get("doc") == [1, {"status": "accepted"}]


@pytest.mark.asyncio
async def test_numeric_vector_copy_does_not_alias_store():
    store = MemoryStore()
    await store.open()
    vector = [0.1, 0.2, 0.3]
    await store.put("vec", {"vector": vector})
    vector[0] = 9.9
    stored = await store.get("vec")
    assert stored == {"vector": [0.1, 0.2, 0.3]}
    loaded = await store.get("vec")
    loaded["vector"][1] = 8.8
    assert (await store.get("vec"))["vector"] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_apply_insert_isolates_nested_objects():
    store = MemoryStore()
    await store.open()
    body = {"items": [1, {"status": "accepted"}]}
    result = await store.apply([Insert("ticket:1", body)])
    assert result.ok is True
    body["items"][1]["status"] = "spoofed"
    stored = await store.get("ticket:1")
    assert stored == {"items": [1, {"status": "accepted"}]}
