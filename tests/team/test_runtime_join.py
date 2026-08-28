"""Join, Session, and Directory operations on the Team Runtime."""

from __future__ import annotations

import asyncio

import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import join_member, profile, make_did


@pytest.mark.asyncio
async def test_join_assigns_qualified_address_and_session(team: Team):
    result = await join_member(team, "writer")
    assert result["address"] == "writer@content-squad"
    assert result["team_name"] == "content-squad"
    assert result["persistence"] == "volatile"
    assert result["limits"]["max_mailbox_depth"] == 1000
    assert result["limits"]["wait_hold_seconds"] == 25.0
    assert result["spec_version"] == "1.0.0-draft"
    assert result["session_token"]
    assert result["instance_id"]


@pytest.mark.asyncio
async def test_join_name_conflict_on_did_clash(team: Team):
    await join_member(team, "writer", agent_did=make_did("writer"))
    with pytest.raises(TeamError) as exc:
        await join_member(team, "editor", agent_did=make_did("writer"))
    assert exc.value.code == "name_conflict"


@pytest.mark.asyncio
async def test_join_name_conflict_on_name_clash(team: Team):
    await join_member(team, "writer", agent_did=make_did("writer"))
    with pytest.raises(TeamError) as exc:
        await join_member(team, "writer", agent_did=make_did("other"))
    assert exc.value.code == "name_conflict"


@pytest.mark.asyncio
async def test_join_reconnects_same_name_and_did(team: Team):
    first = await join_member(team, "writer", agent_did=make_did("writer"))
    second = await join_member(team, "Writer", agent_did=make_did("writer"))
    assert second["address"] == first["address"]
    assert second["session_token"] != first["session_token"]
    # A new instance_id opens another Session; the first stays valid.
    await team.heartbeat(first["session_token"])


@pytest.mark.asyncio
async def test_join_replaces_session_for_same_instance(team: Team):
    first = await join_member(
        team,
        "writer",
        agent_did=make_did("writer"),
        instance_id="8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
    )
    second = await join_member(
        team,
        "writer",
        agent_did=make_did("writer"),
        instance_id="8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
    )
    assert second["instance_id"] == first["instance_id"]
    with pytest.raises(TeamError) as exc:
        await team.heartbeat(first["session_token"])
    assert exc.value.code == "unauthorized"


@pytest.mark.asyncio
async def test_join_rejects_unsupported_version(team: Team):
    with pytest.raises(TeamError) as exc:
        await team.join(
            name="writer",
            agent_did=make_did("writer"),
            profile=profile(),
            spec_version="0.4.0",
        )
    assert exc.value.code == "unsupported_version"


@pytest.mark.asyncio
async def test_disconnect_keeps_membership_and_mailbox(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
            "recipient": "writer",
            "kind": "event",
            "content": "hello",
        },
    )
    assert sent["status"] == "accepted"
    await team.disconnect(writer["session_token"])
    again = await join_member(team, "writer", agent_did=make_did("writer"))
    leased = await team.lease(again["session_token"])
    assert len(leased["deliveries"]) == 1
    assert leased["deliveries"][0]["message"]["id"] == sent["message"]["id"]


@pytest.mark.asyncio
async def test_expired_session_does_not_mutate_on_unauthorized(team: Team):
    short = Team("content-squad", session_ttl_seconds=0.01, sweep_interval_seconds=5)
    await short.start()
    try:
        writer = await join_member(short, "writer")
        await asyncio.sleep(0.05)
        with pytest.raises(TeamError) as exc:
            await short.lease(writer["session_token"])
        assert exc.value.code == "unauthorized"
    finally:
        await short.stop()


@pytest.mark.asyncio
async def test_find_excludes_caller_and_orders_by_relevance(team: Team):
    await join_member(
        team,
        "writer",
        profile=profile(
            summary="Writes drafts and editing notes.",
            skill="drafting",
            description="Write drafts.",
            tags=["writing"],
        ),
    )
    await join_member(
        team,
        "reviewer",
        profile=profile(
            summary="Reviews contracts for missing terms.",
            skill="contract_review",
            description="Review a contract.",
            tags=["contracts"],
        ),
    )
    caller = await join_member(team, "researcher")
    found = await team.find(caller["session_token"], "contract review")
    addresses = [match["address"] for match in found["matches"]]
    assert "researcher@content-squad" not in addresses
    assert addresses[0] == "reviewer@content-squad"


@pytest.mark.asyncio
async def test_get_profile_resolves_unqualified_name(team: Team):
    await join_member(team, "writer")
    caller = await join_member(team, "researcher")
    entry = await team.get_profile(caller["session_token"], "writer")
    assert entry["address"] == "writer@content-squad"
    assert entry["profile"]["summary"]


@pytest.mark.asyncio
async def test_heartbeat_extends_session():
    short = Team("content-squad", session_ttl_seconds=0.4, sweep_interval_seconds=0.05)
    await short.start()
    try:
        writer = await join_member(short, "writer")
        first = await short.heartbeat(writer["session_token"])
        await asyncio.sleep(0.25)
        second = await short.heartbeat(writer["session_token"])
        assert second["session_expires_at"] >= first["session_expires_at"]
        await asyncio.sleep(0.25)
        await short.heartbeat(writer["session_token"])
    finally:
        await short.stop()


@pytest.mark.asyncio
async def test_join_rejects_unknown_profile_fields(team: Team):
    with pytest.raises(TeamError) as exc:
        await team.join(
            name="writer",
            agent_did=make_did("writer"),
            profile={**profile(), "agent_id": "writer"},
        )
    assert exc.value.code == "invalid_request"
