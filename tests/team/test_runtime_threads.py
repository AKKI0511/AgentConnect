"""Thread history window and get_history."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import deadline, join_member


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_delivery_history_window_and_paging(team: Team):
    small = Team("content-squad", delivery_history_limit=2)
    await small.start()
    try:
        writer = await join_member(small, "writer")
        researcher = await join_member(small, "researcher")
        thread_id = _id()
        ids = []
        for i in range(4):
            sent = await small.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": f"turn-{i}",
                    "thread_id": thread_id,
                },
            )
            ids.append(sent["message"]["id"])
            delivery = (await small.lease(writer["session_token"]))["deliveries"][0]
            await small.complete(writer["session_token"], delivery["lease_id"])
        last = await small.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "turn-4",
                "thread_id": thread_id,
            },
        )
        delivery = (await small.lease(writer["session_token"]))["deliveries"][0]
        assert delivery["message"]["id"] == last["message"]["id"]
        assert delivery["history_complete"] is False
        assert [msg["content"] for msg in delivery["history"]] == ["turn-2", "turn-3"]
        page = await small.get_history(researcher["session_token"], thread_id, limit=2)
        assert [msg["content"] for msg in page["messages"]] == ["turn-3", "turn-4"]
        assert page["has_more"] is True
        older = await small.get_history(
            researcher["session_token"],
            thread_id,
            before=page["messages"][0]["id"],
            limit=2,
        )
        assert [msg["content"] for msg in older["messages"]] == ["turn-1", "turn-2"]
    finally:
        await small.stop()


@pytest.mark.asyncio
async def test_get_history_non_participant_is_not_found(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    outsider = await join_member(team, "outsider")
    thread_id = _id()
    await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "private",
            "thread_id": thread_id,
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.get_history(outsider["session_token"], thread_id)
    assert exc.value.code == "not_found"
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.complete(writer["session_token"], delivery["lease_id"])


@pytest.mark.asyncio
async def test_thread_rejects_third_participant(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    thread_id = _id()
    await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "start",
            "thread_id": thread_id,
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.send(
            editor["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "intrude",
                "thread_id": thread_id,
            },
        )
    assert exc.value.code == "forbidden"


@pytest.mark.asyncio
async def test_parent_in_other_thread_is_invalid_request(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    first = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "a",
            "thread_id": _id(),
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "b",
                "thread_id": _id(),
                "parent_id": first["message"]["id"],
            },
        )
    assert exc.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_reply_appends_to_thread_history(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": thread_id,
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "done",
        },
    )
    history = await team.get_history(researcher["session_token"], thread_id)
    kinds = [msg["kind"] for msg in history["messages"]]
    assert kinds == ["request", "response"]
    assert history["messages"][0]["id"] == sent["message"]["id"]
    assert history["messages"][1]["parent_id"] == sent["message"]["id"]


@pytest.mark.asyncio
async def test_delivery_history_truncated_by_bytes():
    small = Team(
        "content-squad",
        delivery_history_limit=10,
        max_message_bytes=400,
    )
    await small.start()
    try:
        writer = await join_member(small, "writer")
        researcher = await join_member(small, "researcher")
        thread_id = _id()
        for i in range(3):
            await small.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "x" * 80,
                    "thread_id": thread_id,
                },
            )
            delivery = (await small.lease(writer["session_token"]))["deliveries"][0]
            await small.complete(writer["session_token"], delivery["lease_id"])
        last = await small.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "x" * 80,
                "thread_id": thread_id,
            },
        )
        delivery = (await small.lease(writer["session_token"]))["deliveries"][0]
        assert delivery["message"]["id"] == last["message"]["id"]
        assert delivery["history_complete"] is False
        assert len(delivery["history"]) < 3
        assert len(delivery["history"]) >= 1
    finally:
        await small.stop()


@pytest.mark.asyncio
async def test_get_history_unknown_before_returns_newest_page(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    contents = []
    for i in range(3):
        sent = await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": f"turn-{i}",
                "thread_id": thread_id,
            },
        )
        contents.append(sent["message"]["content"])
        delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
        await team.complete(writer["session_token"], delivery["lease_id"])
    newest = await team.get_history(researcher["session_token"], thread_id, limit=2)
    missing = await team.get_history(
        researcher["session_token"],
        thread_id,
        before=_id(),
        limit=2,
    )
    assert [msg["content"] for msg in missing["messages"]] == [
        msg["content"] for msg in newest["messages"]
    ]
    assert [msg["content"] for msg in newest["messages"]] == contents[-2:]


@pytest.mark.asyncio
async def test_get_history_invalid_before_is_invalid_request(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "start",
            "thread_id": thread_id,
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.get_history(
            researcher["session_token"],
            thread_id,
            before="not-a-uuid",
        )
    assert exc.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_thread_keeps_messages_needed_by_open_ticket():
    runtime = Team(
        "content-squad",
        thread_message_limit=1,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        thread_id = _id()
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "old",
                "thread_id": thread_id,
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.complete(writer["session_token"], delivery["lease_id"])
        sent = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "keep-me",
                "collect": "ticket",
                "deadline": deadline(20),
                "thread_id": thread_id,
            },
        )
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "newer",
                "thread_id": thread_id,
            },
        )
        extra = (await runtime.lease(writer["session_token"], max_items=10))[
            "deliveries"
        ]
        for item in extra:
            if item["message"]["id"] != sent["message"]["id"]:
                await runtime.complete(writer["session_token"], item["lease_id"])
        await asyncio.sleep(0.2)
        page = await runtime.get_history(researcher["session_token"], thread_id)
        ids = [msg["id"] for msg in page["messages"]]
        assert sent["message"]["id"] in ids
        ticket = await runtime.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert ticket["state"] == "open"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_thread_turns_can_move_across_instances(team: Team):
    first = await join_member(
        team,
        "writer",
        instance_id="8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
    )
    second = await join_member(
        team,
        "writer",
        agent_did=first["agent_did"],
        instance_id="9a1e4f7b-7c2a-5e2f-8b3d-3a1c8d0e2f6b",
    )
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    opening = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "turn-0",
            "thread_id": thread_id,
        },
    )
    first_delivery = (await team.lease(first["session_token"]))["deliveries"][0]
    assert first_delivery["message"]["id"] == opening["message"]["id"]
    await team.complete(first["session_token"], first_delivery["lease_id"])
    follow = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "turn-1",
            "thread_id": thread_id,
        },
    )
    second_delivery = (await team.lease(second["session_token"]))["deliveries"][0]
    assert second_delivery["message"]["id"] == follow["message"]["id"]
    assert second_delivery["history"][0]["id"] == opening["message"]["id"]
    await team.complete(second["session_token"], second_delivery["lease_id"])


@pytest.mark.asyncio
async def test_thread_orders_by_seq_when_created_at_ties(team: Team):
    from agentconnect.team.codec import format_timestamp, utc_now

    frozen = utc_now()
    frozen_ts = format_timestamp(frozen)
    team._now_pair = lambda: (frozen, frozen_ts)
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    first_id = "ffffffff-ffff-4fff-bfff-ffffffffffff"
    second_id = "00000000-0000-4000-8000-000000000001"
    first = await team.send(
        researcher["session_token"],
        {
            "id": first_id,
            "recipient": "writer",
            "kind": "event",
            "content": "first",
            "thread_id": thread_id,
        },
    )
    second = await team.send(
        researcher["session_token"],
        {
            "id": second_id,
            "recipient": "writer",
            "kind": "event",
            "content": "second",
            "thread_id": thread_id,
        },
    )
    assert first["message"]["created_at"] == second["message"]["created_at"]
    assert first["message"]["seq"] == 1
    assert second["message"]["seq"] == 2
    page = await team.get_history(researcher["session_token"], thread_id)
    assert [msg["id"] for msg in page["messages"]] == [first_id, second_id]
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.complete(writer["session_token"], delivery["lease_id"])


@pytest.mark.asyncio
async def test_unthreaded_message_omits_seq(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {"id": _id(), "recipient": "writer", "kind": "event", "content": "note"},
    )
    assert "seq" not in sent["message"]
    assert "thread_id" not in sent["message"]


@pytest.mark.asyncio
async def test_reply_assigns_next_seq(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": thread_id,
        },
    )
    assert sent["message"]["seq"] == 1
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    replied = await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "done",
        },
    )
    assert replied["ticket"]["response"]["seq"] == 2
    history = await team.get_history(researcher["session_token"], thread_id)
    assert [msg["seq"] for msg in history["messages"]] == [1, 2]


@pytest.mark.asyncio
async def test_follow_up_names_one_parent_and_keeps_trace(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    first = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "one",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": thread_id,
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "answer-one",
        },
    )
    follow = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "merged",
            "thread_id": thread_id,
            "parent_id": first["message"]["id"],
        },
    )
    assert follow["message"]["parent_id"] == first["message"]["id"]
    assert follow["message"]["trace_id"] == first["message"]["trace_id"]
    assert "parent_ids" not in follow["message"]
    leftover = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.complete(writer["session_token"], leftover["lease_id"])


@pytest.mark.asyncio
async def test_three_member_thread_authorizes_every_participant(team: Team):
    from agentconnect.team import threads as threads_mod

    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    thread_id = _id()
    msg_id = _id()
    store = team._store
    assert store is not None
    message = {
        "id": msg_id,
        "sender": researcher["address"],
        "recipient": writer["address"],
        "kind": "event",
        "content": "seed",
        "created_at": "2026-08-18T15:00:00.000000Z",
        "trace_id": _id(),
        "thread_id": thread_id,
        "seq": 1,
    }
    await store.put(f"msg:{msg_id}", message)
    await threads_mod.save_thread(
        store,
        {
            "id": thread_id,
            "participants": sorted(
                [
                    researcher["address"],
                    writer["address"],
                    editor["address"],
                ]
            ),
            "message_ids": [msg_id],
            "next_seq": 2,
        },
    )
    page = await team.get_history(editor["session_token"], thread_id)
    assert page["messages"][0]["id"] == msg_id
    sent = await team.send(
        editor["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "from-editor",
            "thread_id": thread_id,
        },
    )
    assert sent["message"]["seq"] == 2
    leftover = (await team.lease(writer["session_token"], max_items=10))["deliveries"]
    for item in leftover:
        await team.complete(writer["session_token"], item["lease_id"])
