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
