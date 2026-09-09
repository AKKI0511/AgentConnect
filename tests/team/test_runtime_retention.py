"""Ticket replay window, Thread trim, and Message-id reuse."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.team import Team, TeamError
from agentconnect.team.codec import json_size
from agentconnect.team.retention import (
    RETAINED_BYTES_KEY,
    reclaim_event_replay,
    reclaim_inactive_lease,
    reclaim_ticket_records,
)
from agentconnect.team.store.memory import MemoryStore
import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.tickets as tickets_mod
from tests.team.conftest import deadline, join_member


def _id() -> str:
    return str(uuid.uuid4())


def _msg_body_bytes(store: MemoryStore) -> int:
    total = 0
    for key, (value, _version) in store._docs.items():
        if key.startswith("msg:") and isinstance(value, dict):
            total += json_size(value)
    return total


async def _counter(store) -> int:
    value = await store.get(RETAINED_BYTES_KEY)
    return 0 if value is None else int(value)


@pytest.mark.asyncio
async def test_id_reusable_after_all_references_reclaimed():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        message_id = _id()
        await runtime.send(
            researcher["session_token"],
            {
                "id": message_id,
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "ticket",
                "deadline": deadline(1.2),
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
        await asyncio.sleep(2.5)
        with pytest.raises(TeamError) as exc:
            await runtime.get_result(researcher["session_token"], message_id)
        assert exc.value.code == "not_found"
        again = await runtime.send(
            researcher["session_token"],
            {
                "id": message_id,
                "recipient": "writer",
                "kind": "request",
                "content": "work-again",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        assert again["status"] == "ticketed"
        assert again["message"]["content"] == "work-again"
        assert again["ticket"]["state"] == "open"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_replay_still_works_after_deadline_within_horizon():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=8,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        body = {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(1.0),
        }
        first = await runtime.send(researcher["session_token"], body)
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
        await asyncio.sleep(1.2)
        replayed = await runtime.send(researcher["session_token"], body)
        assert replayed["message"]["id"] == first["message"]["id"]
        ticket = await runtime.get_result(
            researcher["session_token"], first["message"]["id"]
        )
        assert ticket["state"] == "completed"
        assert ticket["response"]["content"] == "done"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_history_isolates_expired_id_from_new_private_thread():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        thread_message_limit=50,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        editor = await join_member(runtime, "editor")
        reviewer = await join_member(runtime, "reviewer")
        thread_t = _id()
        message_id = _id()
        await runtime.send(
            researcher["session_token"],
            {
                "id": message_id,
                "recipient": "writer",
                "kind": "event",
                "content": "alpha-to-bravo",
                "thread_id": thread_t,
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        await asyncio.sleep(1.6)
        thread_u = _id()
        with pytest.raises(TeamError) as exc:
            await runtime.send(
                editor["session_token"],
                {
                    "id": message_id,
                    "recipient": "reviewer",
                    "kind": "event",
                    "content": "private-charlie-delta",
                    "thread_id": thread_u,
                },
            )
        assert exc.value.code == "id_conflict"
        page = await runtime.get_history(researcher["session_token"], thread_t)
        texts = [item["content"] for item in page["messages"]]
        assert "alpha-to-bravo" in texts
        assert "private-charlie-delta" not in texts
        assert all(item["thread_id"] == thread_t for item in page["messages"])
        seqs = [item["seq"] for item in page["messages"]]
        assert seqs == sorted(seqs)
        leased = await runtime.lease(writer["session_token"])
        assert leased["deliveries"] == []
        store = runtime._store
        assert store is not None
        body = await store.get(f"msg:{message_id}")
        assert body is not None
        assert body["content"] == "alpha-to-bravo"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_queued_events_survive_thread_count_trim():
    runtime = Team(
        "content-squad",
        thread_message_limit=2,
        sweep_interval_seconds=0.05,
        replay_horizon_seconds=1,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer", max_in_flight=4)
        researcher = await join_member(runtime, "researcher")
        thread_id = _id()
        ids = []
        for index in range(4):
            sent = await runtime.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": f"turn-{index}",
                    "thread_id": thread_id,
                },
            )
            ids.append(sent["message"]["id"])
        store = runtime._store
        assert store is not None
        for message_id in ids:
            assert await store.get(f"msg:{message_id}") is not None
        leased = await runtime.lease(writer["session_token"], max_items=4)
        delivered = [item["message"]["id"] for item in leased["deliveries"]]
        assert set(delivered) == set(ids)
        for item in leased["deliveries"]:
            await runtime.complete(writer["session_token"], item["lease_id"])
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_queued_event_survives_replay_horizon():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "still-queued",
            },
        )
        await asyncio.sleep(1.6)
        store = runtime._store
        assert store is not None
        assert await store.get(f"msg:{sent['message']['id']}") is not None
        leased = await runtime.lease(writer["session_token"])
        assert leased["deliveries"][0]["message"]["id"] == sent["message"]["id"]
        assert leased["deliveries"][0]["message"]["content"] == "still-queued"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_leased_event_survives_replay_horizon():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=8,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "leased",
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await asyncio.sleep(1.6)
        done = await runtime.complete(writer["session_token"], delivery["lease_id"])
        public = done if isinstance(done, dict) else done.model_dump()
        assert not public.get("ticket")
        store = runtime._store
        assert store is not None
        assert await store.get(f"msg:{sent['message']['id']}") is None
        assert await _counter(store) == _msg_body_bytes(store)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_thread_trim_deletes_unowned_bodies_after_replay():
    runtime = Team(
        "content-squad",
        thread_message_limit=2,
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer", max_in_flight=4)
        researcher = await join_member(runtime, "researcher")
        thread_id = _id()
        ids = []
        for index in range(4):
            sent = await runtime.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": f"turn-{index}",
                    "thread_id": thread_id,
                },
            )
            ids.append(sent["message"]["id"])
        leased = await runtime.lease(writer["session_token"], max_items=4)
        for item in leased["deliveries"]:
            await runtime.complete(writer["session_token"], item["lease_id"])
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "trim-trigger",
                "thread_id": thread_id,
            },
        )
        await asyncio.sleep(1.8)
        store = runtime._store
        assert store is not None
        page = await runtime.get_history(researcher["session_token"], thread_id)
        remaining = [item["id"] for item in page["messages"]]
        assert ids[0] not in remaining
        assert ids[1] not in remaining
        assert await store.get(f"msg:{ids[0]}") is None
        assert await store.get(f"msg:{ids[1]}") is None
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_complete_replay_lasts_until_request_deadline():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=20,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "ticket",
                "deadline": deadline(8),
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        first = await runtime.complete(writer["session_token"], delivery["lease_id"])
        assert first["ticket"]["state"] == "declined"
        await asyncio.sleep(1.2)
        again = await runtime.complete(writer["session_token"], delivery["lease_id"])
        assert again["ticket"]["state"] == "declined"
        assert again["ticket"]["id"] == sent["message"]["id"]
        ticket = await runtime.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert ticket["state"] == "declined"
    finally:
        await runtime.stop()


@pytest.mark.parametrize("outcome", ["completed", "failed", "declined", "expired"])
@pytest.mark.asyncio
async def test_terminal_replies_are_reclaimed(outcome: str):
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=8,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        request_id = _id()
        reply_id = _id()
        await runtime.send(
            researcher["session_token"],
            {
                "id": request_id,
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "ticket",
                "deadline": deadline(1.3),
            },
        )
        if outcome != "expired":
            delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
            if outcome == "declined":
                await runtime.complete(writer["session_token"], delivery["lease_id"])
            elif outcome == "failed":
                await runtime.reply(
                    writer["session_token"],
                    {
                        "id": reply_id,
                        "lease_id": delivery["lease_id"],
                        "outcome": "failed",
                        "error": {"code": "handler_failed", "message": "nope"},
                    },
                )
            else:
                await runtime.reply(
                    writer["session_token"],
                    {
                        "id": reply_id,
                        "lease_id": delivery["lease_id"],
                        "outcome": "completed",
                        "content": "done",
                    },
                )
        await asyncio.sleep(2.8)
        store = runtime._store
        assert store is not None
        assert await store.get(f"ticket:{request_id}") is None
        assert await store.get(f"send:{request_id}") is None
        assert await store.get(f"msg:{request_id}") is None
        if outcome in {"completed", "failed"}:
            assert await store.get(f"msg:{reply_id}") is None
            assert await store.get(f"reply:{reply_id}") is None
        assert await _counter(store) == _msg_body_bytes(store)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_cleanup_retries_when_byte_counter_conflicts():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=30,
        sweep_interval_seconds=30,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        request_id = _id()
        await runtime.send(
            researcher["session_token"],
            {
                "id": request_id,
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        inner = runtime._store
        assert isinstance(inner, MemoryStore)
        ticket = await tickets_mod.load_ticket(inner, request_id)
        assert ticket is not None
        extra_id = _id()

        class _HookStore:
            def __init__(self, wrapped: MemoryStore) -> None:
                self._inner = wrapped
                self._armed = True

            def __getattr__(self, name: str):
                return getattr(self._inner, name)

            async def get_record(self, key: str):
                record = await self._inner.get_record(key)
                if key == RETAINED_BYTES_KEY and self._armed:
                    self._armed = False
                    await runtime.send(
                        researcher["session_token"],
                        {
                            "id": extra_id,
                            "recipient": "writer",
                            "kind": "event",
                            "content": "interleaved",
                        },
                    )
                return record

        runtime._store = _HookStore(inner)
        await reclaim_ticket_records(
            runtime._store, ticket, byte_limit=runtime.max_retained_bytes
        )
        runtime._store = inner
        assert await inner.get(f"ticket:{request_id}") is None
        assert await inner.get(f"send:{request_id}") is None
        assert await inner.get(f"msg:{request_id}") is None
        extra = await inner.get(f"msg:{extra_id}")
        assert extra is not None
        assert extra["content"] == "interleaved"
        assert await inner.get(f"send:{extra_id}") is not None
        assert await _counter(inner) == _msg_body_bytes(inner)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_retained_byte_admission_counts_canonical_bodies():
    runtime = Team(
        "content-squad",
        max_retained_bytes=3000,
        thread_message_limit=1,
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        thread_id = _id()
        accepted = 0
        for index in range(12):
            try:
                sent = await runtime.send(
                    researcher["session_token"],
                    {
                        "id": _id(),
                        "recipient": "writer",
                        "kind": "event",
                        "content": f"payload-{index}-" + ("n" * 80),
                        "thread_id": thread_id,
                    },
                )
            except TeamError as exc:
                assert exc.code == "busy"
                break
            accepted += 1
            delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
            assert delivery["message"]["id"] == sent["message"]["id"]
            await runtime.complete(writer["session_token"], delivery["lease_id"])
        assert 1 <= accepted < 12
        store = runtime._store
        assert isinstance(store, MemoryStore)
        for key, (value, _version) in store._docs.items():
            if key.startswith("send:") and isinstance(value, dict):
                assert "result" not in value
                assert "message" not in value
        assert await _counter(store) == _msg_body_bytes(store)
        rejected_id = _id()
        with pytest.raises(TeamError) as exc:
            await runtime.send(
                researcher["session_token"],
                {
                    "id": rejected_id,
                    "recipient": "writer",
                    "kind": "event",
                    "content": "n" * 400,
                    "thread_id": thread_id,
                },
            )
        assert exc.value.code == "busy"
        assert await store.get(f"msg:{rejected_id}") is None
        assert await store.get(f"send:{rejected_id}") is None
        await asyncio.sleep(1.8)
        again = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "after-reclaim",
                "thread_id": thread_id,
            },
        )
        assert again["status"] == "accepted"
        assert await _counter(store) == _msg_body_bytes(store)
        assert await _counter(store) <= 3000
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_ids_only_does_not_load_history_bodies():
    runtime = Team(
        "content-squad",
        sweep_interval_seconds=0.05,
        thread_message_limit=50,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer", delivery_history="ids")
        researcher = await join_member(runtime, "researcher")
        thread_id = _id()
        first = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "old",
                "thread_id": thread_id,
            },
        )
        await runtime.complete(
            writer["session_token"],
            (await runtime.lease(writer["session_token"]))["deliveries"][0]["lease_id"],
        )
        second = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "new",
                "thread_id": thread_id,
            },
        )
        leased = await runtime.lease(writer["session_token"])
        delivered = [
            item
            for item in leased["deliveries"]
            if item["message"]["id"] == second["message"]["id"]
        ]
        assert delivered
        assert first["message"]["id"] in delivered[0]["history_ids"]
        assert delivered[0]["history"] == []
        page = await runtime.get_history(researcher["session_token"], thread_id)
        page_ids = [item["id"] for item in page["messages"]]
        assert first["message"]["id"] in page_ids
        assert second["message"]["id"] in page_ids
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_unthreaded_event_reclaimed_when_replay_expires_before_complete():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=8,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "before-complete",
            },
        )
        message_id = sent["message"]["id"]
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await asyncio.sleep(1.6)
        store = runtime._store
        assert isinstance(store, MemoryStore)
        assert await store.get(f"send:{message_id}") is None
        assert await store.get(f"msg:{message_id}") is not None
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        assert await store.get(f"msg:{message_id}") is None
        assert await _counter(store) == _msg_body_bytes(store)
        await asyncio.sleep(1.6)
        assert await store.get(f"msg:{message_id}") is None
        assert await store.get(f"complete:{delivery['lease_id']}") is None
        assert await _counter(store) == _msg_body_bytes(store)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_unthreaded_event_reclaimed_when_replay_expires_after_complete():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=8,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "after-complete",
            },
        )
        message_id = sent["message"]["id"]
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        store = runtime._store
        assert store is not None
        assert await store.get(f"send:{message_id}") is not None
        assert await store.get(f"msg:{message_id}") is not None
        await asyncio.sleep(1.6)
        assert await store.get(f"send:{message_id}") is None
        assert await store.get(f"msg:{message_id}") is None
        assert await _counter(store) == _msg_body_bytes(store)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_threaded_event_kept_after_replay_expires_and_complete():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=8,
        thread_message_limit=50,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        thread_id = _id()
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "keep-history",
                "thread_id": thread_id,
            },
        )
        message_id = sent["message"]["id"]
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await asyncio.sleep(1.6)
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        store = runtime._store
        assert store is not None
        body = await store.get(f"msg:{message_id}")
        assert body is not None
        assert body["content"] == "keep-history"
        page = await runtime.get_history(researcher["session_token"], thread_id)
        assert message_id in [item["id"] for item in page["messages"]]
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_unthreaded_event_cycles_restore_retained_bytes():
    runtime = Team(
        "content-squad",
        max_retained_bytes=3000,
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        lease_ttl_seconds=8,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        store = None
        for index in range(4):
            sent = await runtime.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": f"cycle-{index}-" + ("n" * 80),
                },
            )
            delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
            await asyncio.sleep(1.6)
            await runtime.complete(writer["session_token"], delivery["lease_id"])
            store = runtime._store
            assert isinstance(store, MemoryStore)
            assert await store.get(f"msg:{sent['message']['id']}") is None
            assert await _counter(store) == _msg_body_bytes(store)
            assert await _counter(store) <= 3000
        assert store is not None
        again = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "after-cycles",
            },
        )
        assert again["status"] == "accepted"
        assert await _counter(store) == _msg_body_bytes(store)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_complete_reclaim_retries_when_byte_counter_conflicts():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=30,
        lease_ttl_seconds=20,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "leased-then-expired",
            },
        )
        message_id = sent["message"]["id"]
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        inner = runtime._store
        assert isinstance(inner, MemoryStore)
        await reclaim_event_replay(
            inner, message_id, byte_limit=runtime.max_retained_bytes
        )
        assert await inner.get(f"send:{message_id}") is None
        assert await inner.get(f"msg:{message_id}") is not None
        extra_id = _id()

        class _HookStore:
            def __init__(self, wrapped: MemoryStore) -> None:
                self._inner = wrapped
                self._armed = True

            def __getattr__(self, name: str):
                return getattr(self._inner, name)

            async def get_record(self, key: str):
                record = await self._inner.get_record(key)
                if key == RETAINED_BYTES_KEY and self._armed:
                    self._armed = False
                    await runtime.send(
                        researcher["session_token"],
                        {
                            "id": extra_id,
                            "recipient": "writer",
                            "kind": "event",
                            "content": "during-complete",
                        },
                    )
                return record

        runtime._store = _HookStore(inner)
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        runtime._store = inner
        assert await inner.get(f"msg:{message_id}") is None
        extra = await inner.get(f"msg:{extra_id}")
        assert extra is not None
        assert extra["content"] == "during-complete"
        assert await _counter(inner) == _msg_body_bytes(inner)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_inactive_lease_reclaims_unowned_body_after_ack():
    runtime = Team(
        "content-squad",
        replay_horizon_seconds=1,
        sweep_interval_seconds=30,
        lease_ttl_seconds=20,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "ack-without-complete-commit",
            },
        )
        message_id = sent["message"]["id"]
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        store = runtime._store
        assert isinstance(store, MemoryStore)
        await reclaim_event_replay(
            store, message_id, byte_limit=runtime.max_retained_bytes
        )
        assert await store.get(f"send:{message_id}") is None
        assert await mailbox_mod.acknowledge(
            store,
            str(writer["address"]),
            message_id,
            delivery["lease_id"],
        )
        await mailbox_mod.deactivate_lease(
            store, delivery["lease_id"], retain_until=sent["message"]["created_at"]
        )
        assert await store.get(f"msg:{message_id}") is not None
        extra_id = _id()

        class _HookStore:
            def __init__(self, wrapped: MemoryStore) -> None:
                self._inner = wrapped
                self._armed = True

            def __getattr__(self, name: str):
                return getattr(self._inner, name)

            async def get_record(self, key: str):
                record = await self._inner.get_record(key)
                if key == RETAINED_BYTES_KEY and self._armed:
                    self._armed = False
                    await runtime.send(
                        researcher["session_token"],
                        {
                            "id": extra_id,
                            "recipient": "writer",
                            "kind": "event",
                            "content": "during-lease-reclaim",
                        },
                    )
                return record

        runtime._store = _HookStore(store)
        await reclaim_inactive_lease(
            runtime._store,
            delivery["lease_id"],
            byte_limit=runtime.max_retained_bytes,
        )
        runtime._store = store
        assert await store.get(f"msg:{message_id}") is None
        extra = await store.get(f"msg:{extra_id}")
        assert extra is not None
        assert extra["content"] == "during-lease-reclaim"
        assert await _counter(store) == _msg_body_bytes(store)
    finally:
        await runtime.stop()
