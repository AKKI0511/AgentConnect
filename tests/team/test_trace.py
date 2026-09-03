"""Trace timeline recorded by the Runtime."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from tests.team.conftest import deadline, join_member, profile

pytestmark = pytest.mark.asyncio


def _soon(seconds: float = 0.2) -> str:
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def test_trace_records_accept_lease_reply(team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher", profile=profile("Researches."))
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "recipient": "writer",
            "kind": "request",
            "content": "draft this",
            "collect": "ticket",
            "deadline": deadline(5),
        },
    )
    trace_id = sent["message"]["trace_id"]
    leased = await team.lease(writer["session_token"])
    delivery = leased["deliveries"][0]
    await team.reply(
        writer["session_token"],
        {
            "id": "22222222-2222-4222-8222-222222222222",
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "done",
        },
    )
    operator = await team.ensure_operator_session()
    result = await team.get_trace(operator, trace_id)
    types = [event["type"] for event in result["events"]]
    assert types == ["accepted", "ticket_opened", "leased", "replied"]
    assert result["events"][-1]["detail"]["outcome"] == "completed"


async def test_trace_expired_never_leased(team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "recipient": "writer",
            "kind": "request",
            "content": "too slow",
            "collect": "ticket",
            "deadline": _soon(0.05),
        },
    )
    trace_id = sent["message"]["trace_id"]
    await asyncio.sleep(0.1)
    await team.get_result(researcher["session_token"], sent["message"]["id"])
    operator = await team.ensure_operator_session()
    result = await team.get_trace(operator, trace_id)
    types = [event["type"] for event in result["events"]]
    assert types[0] == "accepted"
    assert "ticket_opened" in types
    assert "leased" not in types
    assert types[-1] == "ticket_closed"
    assert result["events"][-1]["detail"]["state"] == "expired"


async def test_replay_send_does_not_duplicate_trace(team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    body = {
        "id": "44444444-4444-4444-8444-444444444444",
        "recipient": "writer",
        "kind": "event",
        "content": "ping",
    }
    first = await team.send(researcher["session_token"], body)
    await team.send(researcher["session_token"], body)
    operator = await team.ensure_operator_session()
    result = await team.get_trace(operator, first["message"]["trace_id"])
    assert [event["type"] for event in result["events"]] == ["accepted"]


async def test_member_reads_own_trace_stranger_gets_not_found(team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    outsider = await join_member(team, "editor")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "55555555-5555-4555-8555-555555555555",
            "recipient": "writer",
            "kind": "event",
            "content": "note",
        },
    )
    trace_id = sent["message"]["trace_id"]
    own = await team.get_trace(researcher["session_token"], trace_id)
    assert own["events"][0]["type"] == "accepted"
    with pytest.raises(Exception) as exc:
        await team.get_trace(outsider["session_token"], trace_id)
    assert exc.value.code == "not_found"
    # writer is the recipient named in the accepted event
    peer = await team.get_trace(writer["session_token"], trace_id)
    assert peer["trace_id"] == trace_id


async def test_trace_complete_declines_request(team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "88888888-8888-4888-8888-888888888888",
            "recipient": "writer",
            "kind": "request",
            "content": "skip this",
            "collect": "ticket",
            "deadline": deadline(5),
        },
    )
    leased = await team.lease(writer["session_token"])
    await team.complete(writer["session_token"], leased["deliveries"][0]["lease_id"])
    operator = await team.ensure_operator_session()
    result = await team.get_trace(operator, sent["message"]["trace_id"])
    types = [event["type"] for event in result["events"]]
    assert types == ["accepted", "ticket_opened", "leased", "completed"]
    assert result["events"][-1]["detail"].get("declined") is True


async def test_watch_queue_receives_accepted(team):
    operator = await team.ensure_operator_session()
    queue = await team.subscribe_trace_events(operator)
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {
            "id": "99999999-9999-4999-8999-999999999999",
            "recipient": "writer",
            "kind": "event",
            "content": "ping",
        },
    )
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["type"] == "accepted"
    await team.unsubscribe_trace_events(operator, queue)


async def test_unknown_trace_is_not_found(team):
    operator = await team.ensure_operator_session()
    with pytest.raises(Exception) as exc:
        await team.get_trace(operator, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert exc.value.code == "not_found"


async def test_fanout_member_sees_own_leg_and_parent_id(team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    root = await team.send(
        researcher["session_token"],
        {
            "id": "aaaa1111-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
            "recipient": "writer",
            "kind": "request",
            "content": "outline",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    writer_delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    child = await team.send(
        writer["session_token"],
        {
            "id": "bbbb2222-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
            "recipient": "editor",
            "kind": "request",
            "content": "review",
            "collect": "ticket",
            "deadline": deadline(20),
            "parent_id": root["message"]["id"],
        },
    )
    assert child["message"]["trace_id"] == root["message"]["trace_id"]
    assert child["message"]["parent_id"] == root["message"]["id"]
    editor_delivery = (await team.lease(editor["session_token"]))["deliveries"][0]
    await team.reply(
        editor["session_token"],
        {
            "id": "cccc3333-cccc-4ccc-8ccc-ccccccccccc1",
            "lease_id": editor_delivery["lease_id"],
            "outcome": "completed",
            "content": "looks good",
        },
    )
    await team.reply(
        writer["session_token"],
        {
            "id": "dddd4444-dddd-4ddd-8ddd-ddddddddddd1",
            "lease_id": writer_delivery["lease_id"],
            "outcome": "completed",
            "content": "done",
        },
    )
    trace_id = root["message"]["trace_id"]
    operator = await team.ensure_operator_session()
    full = await team.get_trace(operator, trace_id)
    accepted = [event for event in full["events"] if event["type"] == "accepted"]
    assert [event["message_id"] for event in accepted] == [
        root["message"]["id"],
        child["message"]["id"],
    ]
    assert "parent_id" not in accepted[0]
    assert accepted[1]["parent_id"] == root["message"]["id"]

    editor_view = await team.get_trace(editor["session_token"], trace_id)
    editor_ids = {event.get("message_id") for event in editor_view["events"]}
    assert root["message"]["id"] not in editor_ids
    assert child["message"]["id"] in editor_ids
    editor_accepted = [
        event for event in editor_view["events"] if event["type"] == "accepted"
    ]
    assert editor_accepted[0]["parent_id"] == root["message"]["id"]

    researcher_view = await team.get_trace(researcher["session_token"], trace_id)
    researcher_ids = {event.get("message_id") for event in researcher_view["events"]}
    researcher_types = [event["type"] for event in researcher_view["events"]]
    assert root["message"]["id"] in researcher_ids
    assert child["message"]["id"] not in researcher_ids
    assert "leased" in researcher_types
    assert "replied" in researcher_types

    writer_view = await team.get_trace(writer["session_token"], trace_id)
    writer_ids = {event.get("message_id") for event in writer_view["events"]}
    assert root["message"]["id"] in writer_ids
    assert child["message"]["id"] in writer_ids
