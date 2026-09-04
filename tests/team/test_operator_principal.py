"""Operator is a principal: not hireable, name reserved at start."""

from __future__ import annotations

import uuid

import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import join_member, make_did, profile

pytestmark = pytest.mark.asyncio


def _id() -> str:
    return str(uuid.uuid4())


async def test_teammate_find_never_returns_operator(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    found = await team.find(
        researcher["session_token"], "someone who can draft a summary"
    )
    addresses = [match["address"] for match in found["matches"]]
    assert any(item.startswith("writer@") for item in addresses)
    assert all(not item.startswith("operator@") for item in addresses)
    assert writer["address"] in addresses


async def test_send_to_operator_is_not_found(team: Team):
    writer = await join_member(team, "writer")
    with pytest.raises(TeamError) as exc:
        await team.send(
            writer["session_token"],
            {"id": _id(), "recipient": "operator", "kind": "event", "content": "hi"},
        )
    assert exc.value.code == "not_found"


async def test_get_profile_for_operator_is_not_found(team: Team):
    writer = await join_member(team, "writer")
    with pytest.raises(TeamError) as exc:
        await team.get_profile(writer["session_token"], "operator")
    assert exc.value.code == "not_found"


async def test_join_as_operator_fails_before_and_after_operator_session():
    team = await Team("content-squad").start()
    try:
        with pytest.raises(TeamError) as before:
            await team.join(
                name="operator",
                agent_did=make_did("usurper"),
                profile=profile(),
            )
        assert before.value.code == "name_conflict"
        await team.ensure_operator_session()
        with pytest.raises(TeamError) as after:
            await team.join(
                name="operator",
                agent_did=make_did("usurper-two"),
                profile=profile(),
            )
        assert after.value.code == "name_conflict"
        url = await team.serve()
        assert url
        with pytest.raises(TeamError) as during_serve:
            await team.join(
                name="operator",
                agent_did=make_did("usurper-three"),
                profile=profile(),
            )
        assert during_serve.value.code == "name_conflict"
    finally:
        await team.stop()


async def test_remove_membership_refuses_operator(team: Team):
    with pytest.raises(TeamError) as exc:
        await team.remove_membership("operator")
    assert exc.value.code == "forbidden"
    operator = await team.ensure_operator_session()
    snapshot = await team.status(operator)
    names = {row["name"] for row in snapshot["members"]}
    assert "operator" in names
    by_name = {row["name"]: row for row in snapshot["members"]}
    assert by_name["operator"]["kind"] == "principal"
    assert "mailbox_depth" not in by_name["operator"]
    assert "open_tickets" not in by_name["operator"]
