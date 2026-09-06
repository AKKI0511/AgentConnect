"""Membership identity survives reconnect and does not follow a reused name."""

from __future__ import annotations

import uuid

import pytest

from agentconnect.team import Team, TeamError
from agentconnect.team.errors import IDENTITY_MISSING
from tests.team.conftest import deadline, join_member, make_did, profile


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_replacement_cannot_read_or_trace_predecessor_work(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": thread_id,
        },
    )
    await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "note",
            "thread_id": thread_id,
        },
    )
    await team.remove_membership("researcher")
    impostor = await join_member(team, "researcher", agent_did=make_did("impostor"))
    with pytest.raises(TeamError) as ticket_exc:
        await team.get_result(impostor["session_token"], sent["message"]["id"])
    assert ticket_exc.value.code == "not_found"
    with pytest.raises(TeamError) as history_exc:
        await team.get_history(impostor["session_token"], thread_id)
    assert history_exc.value.code == "not_found"
    with pytest.raises(TeamError) as trace_exc:
        await team.get_trace(impostor["session_token"], sent["message"]["trace_id"])
    assert trace_exc.value.code == "not_found"
    assert (await team.lease(impostor["session_token"]))["deliveries"] == []
    await team.remove_membership("writer")
    replacement_writer = await join_member(
        team, "writer", agent_did=make_did("new-writer")
    )
    assert (await team.lease(replacement_writer["session_token"]))["deliveries"] == []


@pytest.mark.asyncio
async def test_same_did_after_remove_is_a_new_membership(team: Team):
    did = make_did("researcher")
    researcher = await join_member(team, "researcher", agent_did=did)
    await join_member(team, "writer")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "keep",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    await team.remove_membership("researcher")
    again = await join_member(team, "researcher", agent_did=did)
    with pytest.raises(TeamError) as exc:
        await team.get_result(again["session_token"], sent["message"]["id"])
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_reconnect_recovers_tickets_opened_by_the_prior_session(team: Team):
    instance_id = "8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a"
    did = make_did("researcher")
    await join_member(team, "writer")
    first = await join_member(
        team, "researcher", agent_did=did, instance_id=instance_id
    )
    sent = await team.send(
        first["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "recover",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    second = await join_member(
        team, "researcher", agent_did=did, instance_id=instance_id
    )
    ticket = await team.get_result(second["session_token"], sent["message"]["id"])
    assert ticket["id"] == sent["message"]["id"]
    assert ticket["state"] == "open"


@pytest.mark.asyncio
async def test_operator_send_stamps_the_operator_did(team: Team):
    writer = await join_member(team, "writer")
    operator = await team.ensure_operator_session()
    member = await team._get_member("operator")
    assert member is not None
    sent = await team.send(
        operator,
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "from-operator",
        },
    )
    assert sent["message"]["sender_did"] == member["agent_did"]
    assert "sender_membership_id" not in sent["message"]
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    assert delivery["message"]["sender_did"] == member["agent_did"]


@pytest.mark.asyncio
async def test_sender_did_survives_a_directory_profile_change(team: Team):
    did = make_did("researcher")
    await join_member(team, "writer")
    first = await join_member(
        team, "researcher", agent_did=did, profile=profile("Researches notes.")
    )
    await join_member(
        team,
        "researcher",
        agent_did=did,
        profile=profile("Now writes headlines."),
    )
    sent = await team.send(
        first["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "still-me",
        },
    )
    assert sent["message"]["sender_did"] == did
    stored = await team._ensure_started().get(f"msg:{sent['message']['id']}")
    assert stored["sender_did"] == did
    assert (
        stored["sender_membership_id"]
        == (await team._get_member("researcher"))["membership_id"]
    )


_USER_KEYS = {
    "sender_membership_id": "keep-sender",
    "recipient_membership_id": "keep-recipient",
    "requester_membership_id": "keep-requester",
    "actor_membership_id": "keep-actor",
}


def _assert_user_json(payload: dict) -> None:
    assert payload["content"] == _USER_KEYS
    assert payload["metadata"] == {"nested": dict(_USER_KEYS)}


@pytest.mark.asyncio
async def test_user_json_survives_public_results_and_runtime_ids_stay_private(
    team: Team,
):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    thread_id = _id()
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": dict(_USER_KEYS),
            "metadata": {"nested": dict(_USER_KEYS)},
            "collect": "ticket",
            "deadline": deadline(20),
            "thread_id": thread_id,
        },
    )
    public_message = sent["message"]
    _assert_user_json(public_message)
    assert "sender_membership_id" not in public_message
    assert "recipient_membership_id" not in public_message
    assert "requester_membership_id" not in sent["ticket"]
    follow = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": dict(_USER_KEYS),
            "metadata": {"nested": dict(_USER_KEYS)},
            "thread_id": thread_id,
        },
    )
    stored = await team._ensure_started().get(f"msg:{public_message['id']}")
    assert (
        stored["sender_membership_id"]
        == (await team._get_member("researcher"))["membership_id"]
    )
    delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    _assert_user_json(delivery["message"])
    assert "sender_membership_id" not in delivery["message"]
    replied = await team.reply(
        writer["session_token"],
        {
            "id": _id(),
            "lease_id": delivery["lease_id"],
            "outcome": "completed",
            "content": dict(_USER_KEYS),
        },
    )
    assert "requester_membership_id" not in replied["ticket"]
    assert replied["ticket"]["response"]["content"] == _USER_KEYS
    assert "sender_membership_id" not in replied["ticket"]["response"]
    follow_delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
    assert follow_delivery["message"]["id"] == follow["message"]["id"]
    assert follow_delivery["history"]
    _assert_user_json(follow_delivery["history"][0])
    assert "sender_membership_id" not in follow_delivery["history"][0]
    ticket = await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert ticket["response"]["content"] == _USER_KEYS
    history = await team.get_history(researcher["session_token"], thread_id)
    _assert_user_json(history["messages"][0])
    assert "sender_membership_id" not in history["messages"][0]
    trace = await team.get_trace(
        researcher["session_token"], sent["message"]["trace_id"]
    )
    assert trace["events"]
    assert all("actor_membership_id" not in event for event in trace["events"])


@pytest.mark.asyncio
async def test_reconnect_without_membership_id_fails_with_reset_guidance(team: Team):
    did = make_did("writer")
    await join_member(team, "writer", agent_did=did)
    store = team._ensure_started()
    member = dict(await team._get_member("writer"))
    member.pop("membership_id")
    await store.put("member:writer", member)
    with pytest.raises(TeamError) as exc:
        await join_member(team, "writer", agent_did=did)
    assert exc.value.code == "internal"
    assert exc.value.message == IDENTITY_MISSING


@pytest.mark.asyncio
async def test_missing_parent_membership_ids_fail_instead_of_address_auth(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "parent",
        },
    )
    store = team._ensure_started()
    stored = dict(await store.get(f"msg:{sent['message']['id']}"))
    stored.pop("sender_membership_id")
    stored.pop("recipient_membership_id")
    await store.put(f"msg:{sent['message']['id']}", stored)
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "child",
                "parent_id": sent["message"]["id"],
            },
        )
    assert exc.value.code == "internal"
    assert exc.value.message == IDENTITY_MISSING


@pytest.mark.asyncio
async def test_get_result_missing_requester_identity_is_internal(team: Team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    store = team._ensure_started()
    ticket = dict(await store.get(f"ticket:{sent['message']['id']}"))
    ticket.pop("requester_membership_id")
    await store.put(f"ticket:{sent['message']['id']}", ticket)
    with pytest.raises(TeamError) as exc:
        await team.get_result(researcher["session_token"], sent["message"]["id"])
    assert exc.value.code == "internal"
    assert exc.value.message == IDENTITY_MISSING


@pytest.mark.asyncio
async def test_lease_missing_recipient_identity_is_internal(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "event",
            "content": "note",
        },
    )
    store = team._ensure_started()
    stored = dict(await store.get(f"msg:{sent['message']['id']}"))
    stored.pop("recipient_membership_id")
    await store.put(f"msg:{sent['message']['id']}", stored)
    with pytest.raises(TeamError) as exc:
        await team.lease(writer["session_token"])
    assert exc.value.code == "internal"
    assert exc.value.message == IDENTITY_MISSING


@pytest.mark.asyncio
async def test_instance_replacement_drops_the_prior_session_document(team: Team):
    instance_id = "8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a"
    did = make_did("writer")
    first = await join_member(team, "writer", agent_did=did, instance_id=instance_id)
    second = await join_member(team, "writer", agent_did=did, instance_id=instance_id)
    store = team._ensure_started()
    assert await store.get(f"session:{first['session_token']}") is None
    assert await store.get(f"instance:writer:{instance_id}") == second["session_token"]
    with pytest.raises(TeamError) as exc:
        await team.heartbeat(first["session_token"])
    assert exc.value.code == "unauthorized"
