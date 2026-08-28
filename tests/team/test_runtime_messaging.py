"""Send, lease, complete, and reply against the in-memory store."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import deadline, join_member, profile


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_send_idempotent_replay_returns_same_message(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    body = {
        "id": _id(),
        "recipient": "writer",
        "kind": "request",
        "content": {"task": "draft"},
        "collect": "ticket",
        "deadline": deadline(20),
    }
    first = await team.send(researcher["session_token"], body)
    second = await team.send(researcher["session_token"], body)
    assert first["message"]["id"] == second["message"]["id"]
    assert first["message"]["created_at"] == second["message"]["created_at"]
    leased = await team.lease(writer["session_token"], max_items=10)
    assert len(leased["deliveries"]) == 1


@pytest.mark.asyncio
async def test_send_id_conflict_on_changed_content(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    message_id = _id()
    await team.send(
        researcher["session_token"],
        {
            "id": message_id,
            "recipient": "writer",
            "kind": "event",
            "content": "one",
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": message_id,
                "recipient": "writer",
                "kind": "event",
                "content": "two",
            },
        )
    assert exc.value.code == "id_conflict"


@pytest.mark.asyncio
async def test_send_id_conflict_from_other_membership(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    editor = await join_member(team, "editor")
    message_id = _id()
    await team.send(
        researcher["session_token"],
        {"id": message_id, "recipient": "writer", "kind": "event", "content": "x"},
    )
    with pytest.raises(TeamError) as exc:
        await team.send(
            editor["session_token"],
            {"id": message_id, "recipient": "writer", "kind": "event", "content": "x"},
        )
    assert exc.value.code == "id_conflict"


@pytest.mark.asyncio
async def test_payload_too_large_mailbox_stays_empty():
    tiny = Team("content-squad", max_message_bytes=80)
    await tiny.start()
    try:
        writer = await join_member(tiny, "writer")
        researcher = await join_member(tiny, "researcher")
        with pytest.raises(TeamError) as exc:
            await tiny.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "n" * 400,
                },
            )
        assert exc.value.code == "payload_too_large"
        leased = await tiny.lease(writer["session_token"])
        assert leased["deliveries"] == []
    finally:
        await tiny.stop()


@pytest.mark.asyncio
async def test_unsupported_collect_mode_creates_nothing(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "stream",
                "deadline": deadline(10),
            },
        )
    assert exc.value.code == "unsupported_collect_mode"
    assert (await team.lease(writer["session_token"]))["deliveries"] == []


@pytest.mark.asyncio
async def test_address_outside_team(team: Team):
    researcher = await join_member(team, "researcher")
    await join_member(team, "writer")
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer@legal.example.com",
                "kind": "event",
                "content": "x",
            },
        )
    assert exc.value.code == "address_outside_team"


@pytest.mark.asyncio
async def test_mailbox_busy(team: Team):
    small = Team("content-squad", max_mailbox_depth=1)
    await small.start()
    try:
        await join_member(small, "writer")
        researcher = await join_member(small, "researcher")
        await small.send(
            researcher["session_token"],
            {"id": _id(), "recipient": "writer", "kind": "event", "content": "one"},
        )
        with pytest.raises(TeamError) as exc:
            await small.send(
                researcher["session_token"],
                {"id": _id(), "recipient": "writer", "kind": "event", "content": "two"},
            )
        assert exc.value.code == "busy"
    finally:
        await small.stop()


@pytest.mark.asyncio
async def test_numbers_compare_by_value_for_idempotency(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    message_id = _id()
    await team.send(
        researcher["session_token"],
        {"id": message_id, "recipient": "writer", "kind": "event", "content": {"n": 1}},
    )
    replay = await team.send(
        researcher["session_token"],
        {
            "id": message_id,
            "recipient": "writer",
            "kind": "event",
            "content": {"n": 1.0},
        },
    )
    assert replay["status"] == "accepted"


@pytest.mark.asyncio
async def test_disconnect_releases_lease_and_ticket_stays_open(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    leased = await team.lease(writer["session_token"])
    assert leased["deliveries"][0]["attempt"] == 1
    await team.disconnect(writer["session_token"])
    ticket = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert ticket["state"] == "open"
    writer2 = await join_member(team, "writer")
    leased2 = await team.lease(writer2["session_token"])
    assert leased2["deliveries"][0]["message"]["id"] == sent["message"]["id"]
    assert leased2["deliveries"][0]["attempt"] == 2


@pytest.mark.asyncio
async def test_lease_expiry_increments_attempt(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {"id": _id(), "recipient": "writer", "kind": "event", "content": "x"},
    )
    first = await team.lease(writer["session_token"])
    assert first["deliveries"][0]["attempt"] == 1
    await asyncio.sleep(0.5)
    second = await team.lease(writer["session_token"])
    assert second["deliveries"][0]["message"]["id"] == sent["message"]["id"]
    assert second["deliveries"][0]["attempt"] == 2


@pytest.mark.asyncio
async def test_reply_copies_trace_id_and_does_not_enqueue(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    replied = await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "ok",
        },
    )
    response = replied["ticket"]["response"]
    assert response["trace_id"] == sent["message"]["trace_id"]
    assert response["parent_id"] == sent["message"]["id"]
    inbound = await team.lease(researcher["session_token"])
    assert inbound["deliveries"] == []


@pytest.mark.asyncio
async def test_second_reply_is_ticket_closed_and_increments_late_count(team: Team):
    writer = await join_member(team, "writer", max_in_flight=2)
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "first",
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "second",
            },
        )
    assert exc.value.code == "ticket_closed"
    ticket = await team.get_result(
        researcher["session_token"], delivery["message"]["id"]
    )
    assert ticket["state"] == "completed"
    assert ticket["response"]["content"] == "first"
    assert ticket["late_reply_count"] == 1


@pytest.mark.asyncio
async def test_reply_idempotent_replay(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    body = {
        "id": _id(),
        "lease_id": delivery["lease_id"],
        "outcome": "completed",
        "content": "ok",
    }
    first = await team.reply(writer["session_token"], body)
    second = await team.reply(writer["session_token"], body)
    assert first["ticket"]["response"]["id"] == second["ticket"]["response"]["id"]
    assert second["ticket"]["late_reply_count"] == 0


@pytest.mark.asyncio
async def test_deadline_expires_ticket_and_blocks_reply(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(0.05),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await asyncio.sleep(0.1)
    ticket = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert ticket["state"] == "expired"
    with pytest.raises(TeamError) as exc:
        await team.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "late",
            },
        )
    assert exc.value.code == "ticket_closed"
    again = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert again["state"] == "expired"
    assert again["late_reply_count"] >= 1


@pytest.mark.asyncio
async def test_get_result_twice_identical(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": "ok",
        },
    )
    a = await team.get_result(researcher["session_token"], sent["message"]["id"])
    b = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert a == b


@pytest.mark.asyncio
async def test_complete_declines_reply_expected_request(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    result = await team.complete(writer["session_token"], delivery["lease_id"])
    assert result["ticket"]["state"] == "declined"
    ticket = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert ticket["state"] == "declined"
    assert "error" not in ticket


@pytest.mark.asyncio
async def test_reply_null_content_completes(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    replied = await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": None,
        },
    )
    assert replied["ticket"]["state"] == "completed"
    assert replied["ticket"]["response"]["content"] is None
    ticket = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert ticket["response"]["content"] is None


@pytest.mark.asyncio
async def test_complete_event_has_no_ticket(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {"id": _id(), "recipient": "writer", "kind": "event", "content": "note"},
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    result = await team.complete(writer["session_token"], delivery["lease_id"])
    assert result == {}
    with pytest.raises(TeamError) as exc:
        await team.get_result(researcher["session_token"], delivery["message"]["id"])
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_foreign_lease_id_is_not_found(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {"id": _id(), "recipient": "writer", "kind": "event", "content": "x"},
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    with pytest.raises(TeamError) as exc:
        await team.complete(researcher["session_token"], delivery["lease_id"])
    assert exc.value.code == "not_found"
    still = await team.lease(writer["session_token"])
    assert still["deliveries"] == []


@pytest.mark.asyncio
async def test_get_result_hides_ticket_from_other_member(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    with pytest.raises(TeamError) as exc:
        await team.get_result(writer["session_token"], sent["message"]["id"])
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_collect_wait_returns_terminal_ticket(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")

    async def _respond():
        for _ in range(50):
            leased = await team.lease(writer["session_token"])
            if leased["deliveries"]:
                delivery = leased["deliveries"][0]
                await team.reply(
                    writer["session_token"],
                    {
                        "id": _id(),
                        "lease_id": delivery["lease_id"],
                        "outcome": "completed",
                        "content": "done",
                    },
                )
                return
            await asyncio.sleep(0.02)

    task = asyncio.create_task(_respond())
    result = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "wait",
            "deadline": deadline(10),
        },
    )
    await task
    assert result["status"] == "ticketed"
    assert result["ticket"]["state"] == "completed"


@pytest.mark.asyncio
async def test_failed_reply_stores_handler_failed(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    replied = await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "failed",
            "error": {"code": "handler_failed", "message": "model call failed"},
        },
    )
    assert replied["ticket"]["state"] == "failed"
    ticket = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert ticket["error"]["code"] == "handler_failed"


@pytest.mark.asyncio
async def test_reply_on_event_is_invalid_request(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {"id": _id(), "recipient": "writer", "kind": "event", "content": "x"},
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    with pytest.raises(TeamError) as exc:
        await team.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "nope",
            },
        )
    assert exc.value.code == "invalid_request"
    still = await team.complete(writer["session_token"], delivery["lease_id"])
    assert still == {}


@pytest.mark.asyncio
async def test_open_ticket_survives_short_terminal_retention():
    runtime = Team(
        "content-squad",
        terminal_ticket_retention_seconds=0.05,
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
                "kind": "request",
                "content": "work",
                "collect": "ticket",
                "deadline": deadline(8),
            },
        )
        await asyncio.sleep(0.25)
        ticket = await runtime.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert ticket["state"] == "open"
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "still open",
            },
        )
        done = await runtime.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert done["state"] == "completed"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_callback_collect_is_unsupported(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "callback",
                "deadline": deadline(10),
            },
        )
    assert exc.value.code == "unsupported_collect_mode"


@pytest.mark.asyncio
async def test_wait_hold_returns_open_ticket():
    runtime = Team("content-squad", wait_hold_seconds=0.05)
    await runtime.start()
    try:
        await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        result = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "wait",
                "deadline": deadline(20),
            },
        )
        assert result["status"] == "ticketed"
        assert result["ticket"]["state"] == "open"
        ticket = await runtime.get_result(
            researcher["session_token"], result["ticket"]["id"]
        )
        assert ticket["state"] == "open"
    finally:
        await runtime.stop()
