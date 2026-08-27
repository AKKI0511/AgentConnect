"""Thread history window and get_history."""

from __future__ import annotations

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
