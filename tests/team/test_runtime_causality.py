"""Cross-Thread causal parents copy trace without leaking history."""

from __future__ import annotations

import uuid

import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import deadline, join_member


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_new_thread_may_name_authorized_parent_from_another_thread(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    t1 = _id()
    t2 = _id()
    root = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": t1,
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    child = await team.send(
        writer["session_token"],
        {
            "id": _id(),
            "recipient": "editor",
            "kind": "request",
            "content": "tighten",
            "collect": "ticket",
            "deadline": deadline(15),
            "thread_id": t2,
            "parent_id": root["message"]["id"],
        },
    )
    assert child["message"]["parent_id"] == root["message"]["id"]
    assert child["message"]["trace_id"] == root["message"]["trace_id"]
    assert child["message"]["thread_id"] == t2
    editor_history = await team.get_history(editor["session_token"], t2)
    assert editor_history["messages"][0]["id"] == child["message"]["id"]
    with pytest.raises(TeamError) as exc:
        await team.get_history(editor["session_token"], t1)
    assert exc.value.code == "not_found"
    writer_t1 = await team.get_history(writer["session_token"], t1)
    assert writer_t1["messages"][0]["id"] == root["message"]["id"]
    with pytest.raises(TeamError) as researcher_t2:
        await team.get_history(researcher["session_token"], t2)
    assert researcher_t2.value.code == "not_found"
    await team.complete(writer["session_token"], delivery["lease_id"])
    child_delivery = (await team.lease(editor["session_token"]))["deliveries"][0]
    await team.complete(editor["session_token"], child_delivery["lease_id"])


@pytest.mark.asyncio
async def test_existing_thread_rejects_parent_from_another_thread(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    t1 = _id()
    t2 = _id()
    root = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": t1,
        },
    )
    await team.send(
        writer["session_token"],
        {
            "id": _id(),
            "recipient": "editor",
            "kind": "event",
            "content": "seed t2",
            "thread_id": t2,
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.send(
            writer["session_token"],
            {
                "id": _id(),
                "recipient": "editor",
                "kind": "event",
                "content": "graft",
                "thread_id": t2,
                "parent_id": root["message"]["id"],
            },
        )
    assert exc.value.code == "invalid_request"
    leftover = await team.lease(writer["session_token"], max_items=4)
    for item in leftover["deliveries"]:
        await team.complete(writer["session_token"], item["lease_id"])
    leftover_e = await team.lease(editor["session_token"], max_items=4)
    for item in leftover_e["deliveries"]:
        await team.complete(editor["session_token"], item["lease_id"])


@pytest.mark.asyncio
async def test_unauthorized_parent_is_not_found(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    root = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "private",
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.send(
            editor["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "spoof",
                "parent_id": root["message"]["id"],
            },
        )
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_child_deadline_after_parent_is_rejected(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await join_member(team, "editor")
    root = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(5),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    with pytest.raises(TeamError) as exc:
        await team.send(
            writer["session_token"],
            {
                "id": _id(),
                "recipient": "editor",
                "kind": "request",
                "content": "too long",
                "collect": "ticket",
                "deadline": deadline(30),
                "thread_id": _id(),
                "parent_id": root["message"]["id"],
            },
        )
    assert exc.value.code == "invalid_request"
    await team.complete(writer["session_token"], delivery["lease_id"])


@pytest.mark.asyncio
async def test_foreign_parent_rejected_when_thread_appears_during_apply(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    t1 = _id()
    t2 = _id()
    root = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": t1,
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    store = team._store
    assert store is not None
    orig = store.get_record
    creating = False

    async def wrapped(key):
        nonlocal creating
        rec = await orig(key)
        if key == f"thread:{t2}" and rec is None and not creating:
            creating = True
            await team.send(
                editor["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "seed t2",
                    "thread_id": t2,
                },
            )
            rec = await orig(key)
        return rec

    store.get_record = wrapped  # type: ignore[method-assign]
    with pytest.raises(TeamError) as exc:
        await team.send(
            writer["session_token"],
            {
                "id": _id(),
                "recipient": "editor",
                "kind": "request",
                "content": "graft",
                "collect": "ticket",
                "deadline": deadline(15),
                "thread_id": t2,
                "parent_id": root["message"]["id"],
            },
        )
    assert exc.value.code == "invalid_request"
    leftover = await team.lease(writer["session_token"], max_items=4)
    for item in leftover["deliveries"]:
        await team.complete(writer["session_token"], item["lease_id"])
    leftover_e = await team.lease(editor["session_token"], max_items=4)
    for item in leftover_e["deliveries"]:
        await team.complete(editor["session_token"], item["lease_id"])
    await team.complete(writer["session_token"], delivery["lease_id"])
