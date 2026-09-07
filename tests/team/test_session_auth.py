"""Session resolution: explicit local trust and non-mutating checks."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from agentconnect.team import Team, TeamError
from agentconnect.team.session_auth import (
    allow_loopback_operator,
    session_token_for_request,
)
from tests.team.conftest import join_member, profile

PREFIX = "/agentconnect/v1"


def test_empty_forwarded_header_refuses_operator():
    assert not allow_loopback_operator(
        headers={"x-forwarded-for": ""},
        peer_host="127.0.0.1",
        in_process=False,
    )
    assert not allow_loopback_operator(
        headers={"X-Forwarded-Proto": ""},
        peer_host="127.0.0.1",
        in_process=True,
    )


def test_missing_http_context_is_not_trusted_unless_in_process():
    assert not allow_loopback_operator(headers=None, peer_host=None, in_process=False)
    assert allow_loopback_operator(headers=None, peer_host=None, in_process=True)
    assert allow_loopback_operator(headers={}, peer_host="127.0.0.1", in_process=False)


@pytest.mark.asyncio
async def test_present_empty_authorization_is_unauthorized(team: Team):
    with pytest.raises(TeamError) as exc:
        await session_token_for_request(
            team,
            {"Authorization": ""},
            peer_host="127.0.0.1",
            in_process=False,
        )
    assert exc.value.code == "unauthorized"

    with pytest.raises(TeamError) as exc:
        await session_token_for_request(
            team,
            None,
            peer_host=None,
            in_process=False,
        )
    assert exc.value.code == "unauthorized"


@pytest.mark.asyncio
async def test_in_process_missing_header_is_operator(team: Team):
    token = await session_token_for_request(team, None, in_process=True)
    address = await team.caller_address(token)
    assert address.startswith("operator@")


@pytest.mark.asyncio
async def test_http_auth_does_not_renew_session_expiry():
    team = Team(
        "content-squad",
        session_ttl_seconds=2,
        sweep_interval_seconds=0.05,
    )
    await team.start()
    try:
        writer = await join_member(team, "writer")
        origin = await team.serve()
        token = writer["session_token"]
        before = (await team._get_session(token))["expires_at"]
        async with httpx.AsyncClient() as client:
            found = await client.post(
                origin + PREFIX + "/directory/find",
                json={"query": "someone who can draft a summary"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert found.status_code == 200
            assert "matches" in found.json()
            after_find = (await team._get_session(token))["expires_at"]
            assert after_find == before
            await asyncio.sleep(0.05)
            heartbeat = await client.post(
                origin + PREFIX + "/session/heartbeat",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert heartbeat.status_code == 200
            after = heartbeat.json()["session_expires_at"]
        assert after >= after_find
        session = await team._get_session(token)
        assert session is not None
        assert session["expires_at"] == after
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_expired_disconnected_and_revoked_sessions_are_unauthorized():
    short = Team(
        "content-squad",
        session_ttl_seconds=0.4,
        sweep_interval_seconds=0.05,
    )
    await short.start()
    try:
        writer = await join_member(short, "writer")
        origin = await short.serve()
        token = writer["session_token"]
        await asyncio.sleep(0.6)
        async with httpx.AsyncClient() as client:
            expired = await client.post(
                origin + PREFIX + "/directory/find",
                json={"query": "someone who can draft a summary"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert expired.status_code == 401
    finally:
        await short.stop()

    team = await Team("ops-team").start()
    try:
        member = await join_member(team, "writer")
        url = await team.serve()
        live = member["session_token"]
        await team.disconnect(live)
        async with httpx.AsyncClient() as client:
            disconnected = await client.get(
                url + PREFIX + "/directory/members/writer",
                headers={"Authorization": f"Bearer {live}"},
            )
            assert disconnected.status_code == 401
    finally:
        await team.stop()

    from agentconnect.core.identity import AgentIdentity, issue_identity_proof

    gated = Team(
        "gated-team",
        require_join_auth=True,
        join_challenge_ttl_seconds=60,
        join_token_ttl_seconds=3600,
    )
    await gated.start()
    try:
        identity = AgentIdentity.create_key_based()
        issued = await gated.issue_join_token(name="writer", agent_did=identity.did)
        challenge = await gated.join_challenge()
        proof = issue_identity_proof(identity, challenge)
        joined = await gated.join(
            name="writer",
            agent_did=identity.did,
            profile=profile(),
            join_token=issued["token"],
            identity_proof=proof,
        )
        origin = await gated.serve()
        await gated.revoke_join_token(issued["token"])
        async with httpx.AsyncClient() as client:
            revoked = await client.post(
                origin + PREFIX + "/directory/find",
                json={"query": "someone who can draft a summary"},
                headers={"Authorization": f"Bearer {joined['session_token']}"},
            )
            assert revoked.status_code == 401
    finally:
        await gated.stop()
