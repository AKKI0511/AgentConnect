"""Atomic apply, versioned put, and send/reply acceptance transitions."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.team import Team, TeamError
from agentconnect.team.locks import KeyedLock
from agentconnect.team.codec import utc_now
from agentconnect.team.store import (
    Cas,
    Insert,
    MemoryStore,
    IndexAddIfCardBelow,
)
from tests.team.conftest import deadline, join_member


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_apply_rolls_back_when_an_insert_conflicts():
    store = MemoryStore()
    await store.open()
    assert await store.insert("keep", {"n": 1})
    result = await store.apply(
        [
            Insert("fresh", {"n": 2}),
            Insert("keep", {"n": 3}),
        ]
    )
    assert result.ok is False
    assert result.reason == "exists"
    assert await store.get("fresh") is None
    assert await store.get("keep") == {"n": 1}


@pytest.mark.asyncio
async def test_apply_rolls_back_when_cas_mismatches():
    store = MemoryStore()
    await store.open()
    assert await store.insert("ticket", {"state": "open"})
    record = await store.get_record("ticket")
    assert record is not None
    result = await store.apply(
        [
            Insert("msg", {"id": "1"}),
            Cas("ticket", record.version + 9, {"state": "completed"}),
        ]
    )
    assert result.ok is False
    assert result.reason == "cas"
    assert await store.get("msg") is None
    assert await store.get("ticket") == {"state": "open"}


@pytest.mark.asyncio
async def test_apply_index_cap_is_exact_under_contention():
    store = MemoryStore()
    await store.open()

    async def one(i: int) -> bool:
        result = await store.apply(
            [
                Insert(f"item:{i}", {"id": i}),
                IndexAddIfCardBelow("idx", float(i), str(i), 3),
            ]
        )
        return result.ok

    outcomes = await asyncio.gather(*[one(i) for i in range(12)])
    assert sum(1 for ok in outcomes if ok) == 3
    assert await store.index_card("idx") == 3


@pytest.mark.asyncio
async def test_keyed_lock_cancel_while_waiting_releases_bookkeeping():
    locks = KeyedLock()

    async def holder() -> None:
        async with locks.acquire("k"):
            await asyncio.sleep(1)

    held = asyncio.create_task(holder())
    await asyncio.sleep(0.02)

    async def waiter() -> None:
        async with locks.acquire("k"):
            return None

    waiting = asyncio.create_task(waiter())
    await asyncio.sleep(0.02)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    assert len(locks) == 1
    held.cancel()
    await asyncio.gather(held, return_exceptions=True)
    assert len(locks) == 0


@pytest.mark.asyncio
async def test_concurrent_send_and_lease_never_sees_item_without_message():
    team = Team("content-squad")
    await team.start()
    try:
        writer = await join_member(team, "writer", max_in_flight=16)
        researcher = await join_member(team, "researcher")
        dropped: list[str] = []
        original = team.lease

        async def watching_lease(session_token: str, max_items: int = 1):
            store = team._ensure_started()
            address = "writer@content-squad"
            from agentconnect.team import mailbox as mailbox_mod

            ready = await mailbox_mod.ready_ids(store, address, utc_now(), 32)
            for message_id in ready:
                message = await store.get(f"msg:{message_id}")
                ticket = await store.get(f"ticket:{message_id}")
                if message is None:
                    dropped.append(message_id)
                elif message.get("kind") == "request" and ticket is None:
                    dropped.append(message_id)
            return await original(session_token, max_items)

        team.lease = watching_lease  # type: ignore[method-assign]

        async def send_one(i: int) -> None:
            await team.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "request",
                    "content": i,
                    "collect": "ticket",
                    "deadline": deadline(30),
                },
            )

        await asyncio.gather(
            asyncio.gather(*[send_one(i) for i in range(12)]),
            watching_lease(writer["session_token"], 16),
        )
        assert dropped == []
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_send_and_reply_same_id_conflict(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    shared = _id()
    sent = await team.send(
        researcher["session_token"],
        {
            "id": shared,
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    with pytest.raises(TeamError) as exc:
        await team.reply(
            writer["session_token"],
            {
                "id": shared,
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
    assert exc.value.code == "id_conflict"
    other = _id()
    replied = await team.reply(
        writer["session_token"],
        {
            "id": other,
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "done",
        },
    )
    assert replied["ticket"]["state"] == "completed"
    assert sent["message"]["id"] == shared


@pytest.mark.asyncio
async def test_concurrent_identical_sends_create_one_mailbox_item(team: Team):
    writer = await join_member(team, "writer", max_in_flight=4)
    researcher = await join_member(team, "researcher")
    message_id = _id()
    body = {
        "id": message_id,
        "recipient": "writer",
        "kind": "event",
        "content": "once",
    }
    results = await asyncio.gather(
        team.send(researcher["session_token"], body),
        team.send(researcher["session_token"], body),
    )
    assert results[0]["message"]["id"] == results[1]["message"]["id"]
    assert results[0]["message"]["created_at"] == results[1]["message"]["created_at"]
    leased = await team.lease(writer["session_token"], max_items=10)
    assert len(leased["deliveries"]) == 1


@pytest.mark.asyncio
async def test_concurrent_thread_sends_get_distinct_seq(team: Team):
    writer = await join_member(team, "writer", max_in_flight=20)
    researcher = await join_member(team, "researcher")
    thread_id = _id()

    async def send_one(i: int) -> dict:
        return await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": i,
                "thread_id": thread_id,
            },
        )

    results = await asyncio.gather(*[send_one(i) for i in range(8)])
    seqs = [item["message"]["seq"] for item in results]
    assert sorted(seqs) == list(range(1, 9))
    leased = await team.lease(writer["session_token"], max_items=10)
    assert len(leased["deliveries"]) == 8
