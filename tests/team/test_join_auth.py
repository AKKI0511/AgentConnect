"""Join tokens, DID proofs, revocation, and membership attestations."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from agentconnect.core.identity import AgentIdentity, issue_identity_proof, utc_now
from agentconnect.team import Team, TeamError
from tests.team.conftest import join_member, make_did, profile


async def _auth_team(**kwargs) -> Team:
    runtime = Team(
        "content-squad",
        require_join_auth=True,
        join_challenge_ttl_seconds=60,
        join_token_ttl_seconds=3600,
        session_ttl_seconds=30,
        sweep_interval_seconds=0.05,
        **kwargs,
    )
    await runtime.start()
    return runtime


async def _join_with_proof(
    team: Team,
    identity: AgentIdentity,
    name: str,
    join_token: str,
    **kwargs,
):
    challenge = await team.join_challenge()
    proof = issue_identity_proof(identity, challenge)
    return await team.join(
        name=name,
        agent_did=identity.did,
        profile=kwargs.get("profile") or profile(),
        instance_id=kwargs.get("instance_id"),
        join_token=join_token,
        identity_proof=proof,
    )


@pytest.mark.asyncio
async def test_embedded_join_still_skips_credentials(team: Team):
    result = await join_member(team, "writer")
    assert result["address"] == "writer@content-squad"
    assert result["agent_did"] == make_did("writer")


@pytest.mark.asyncio
async def test_require_auth_rejects_missing_credentials():
    team = await _auth_team()
    try:
        with pytest.raises(TeamError) as exc:
            await join_member(team, "writer")
        assert exc.value.code == "unauthorized"
        assert await team._get_member("writer") is None
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_token_bound_to_did_is_useless_to_another_agent():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    thief = AgentIdentity.create_key_based()
    try:
        issued = await team.issue_join_token(name="writer", agent_did=writer.did)
        with pytest.raises(TeamError) as exc:
            await _join_with_proof(team, thief, "writer", issued["token"])
        assert exc.value.code == "unauthorized"
        assert await team._get_member("writer") is None
        result = await _join_with_proof(team, writer, "writer", issued["token"])
        assert result["agent_did"] == writer.did
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_valid_token_invalid_signature_creates_no_membership():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    other = AgentIdentity.create_key_based()
    try:
        issued = await team.issue_join_token(name="writer", agent_did=writer.did)
        challenge = await team.join_challenge()
        proof = issue_identity_proof(other, challenge)
        with pytest.raises(TeamError) as exc:
            await team.join(
                name="writer",
                agent_did=writer.did,
                profile=profile(),
                join_token=issued["token"],
                identity_proof=proof,
            )
        assert exc.value.code == "unauthorized"
        assert await team._get_member("writer") is None
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_reused_challenge_nonce_is_unauthorized():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    try:
        issued = await team.issue_join_token(name="writer", agent_did=writer.did)
        challenge = await team.join_challenge()
        proof = issue_identity_proof(writer, challenge)
        await team.join(
            name="writer",
            agent_did=writer.did,
            profile=profile(),
            join_token=issued["token"],
            identity_proof=proof,
        )
        with pytest.raises(TeamError) as exc:
            await team.join(
                name="writer",
                agent_did=writer.did,
                profile=profile(),
                instance_id="8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
                join_token=issued["token"],
                identity_proof=proof,
            )
        assert exc.value.code == "unauthorized"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_expired_identity_proof_is_unauthorized():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    try:
        issued = await team.issue_join_token(name="writer", agent_did=writer.did)
        challenge = await team.join_challenge()
        now = int(utc_now().timestamp())
        from agentconnect.core.identity import encode_eddsa_jwt

        proof = encode_eddsa_jwt(
            {
                "iss": writer.did,
                "aud": challenge["audience"],
                "nonce": challenge["nonce"],
                "iat": now - 120,
                "exp": now - 60,
            },
            writer.private_key,
        )
        with pytest.raises(TeamError) as exc:
            await team.join(
                name="writer",
                agent_did=writer.did,
                profile=profile(),
                join_token=issued["token"],
                identity_proof=proof,
            )
        assert exc.value.code == "unauthorized"
        assert await team._get_member("writer") is None
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_revoke_join_token_drops_session_immediately():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    researcher = AgentIdentity.create_key_based()
    try:
        writer_tok = await team.issue_join_token(name="writer", agent_did=writer.did)
        researcher_tok = await team.issue_join_token(
            name="researcher", agent_did=researcher.did
        )
        joined_writer = await _join_with_proof(
            team, writer, "writer", writer_tok["token"]
        )
        joined_researcher = await _join_with_proof(
            team, researcher, "researcher", researcher_tok["token"]
        )
        await team.revoke_join_token(writer_tok["token"])
        with pytest.raises(TeamError) as exc:
            await team.heartbeat(joined_writer["session_token"])
        assert exc.value.code == "unauthorized"
        await team.heartbeat(joined_researcher["session_token"])
        with pytest.raises(TeamError) as replay:
            await _join_with_proof(team, writer, "writer", writer_tok["token"])
        assert replay.value.code == "unauthorized"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_remove_membership_stops_waiting_send():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    researcher = AgentIdentity.create_key_based()
    try:
        writer_tok = await team.issue_join_token(name="writer", agent_did=writer.did)
        researcher_tok = await team.issue_join_token(
            name="researcher", agent_did=researcher.did
        )
        await _join_with_proof(team, writer, "writer", writer_tok["token"])
        joined_researcher = await _join_with_proof(
            team, researcher, "researcher", researcher_tok["token"]
        )
        deadline = (utc_now() + timedelta(seconds=8)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        async def _waiting_send():
            return await team.send(
                joined_researcher["session_token"],
                {
                    "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
                    "recipient": "writer",
                    "kind": "request",
                    "content": "hello",
                    "collect": "wait",
                    "deadline": deadline,
                },
            )

        task = asyncio.create_task(_waiting_send())
        await asyncio.sleep(0.05)
        await team.remove_membership("researcher")
        with pytest.raises(TeamError) as exc:
            await asyncio.wait_for(task, timeout=2)
        assert exc.value.code == "unauthorized"
        with pytest.raises(TeamError) as lease_exc:
            await team.lease(joined_researcher["session_token"])
        assert lease_exc.value.code == "unauthorized"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_membership_attestation_is_minted_for_ed25519_did():
    team = await _auth_team()
    writer = AgentIdentity.create_key_based()
    try:
        issued = await team.issue_join_token(name="writer", agent_did=writer.did)
        await _join_with_proof(team, writer, "writer", issued["token"])
        token = await team.membership_attestation("writer")
        assert isinstance(token, str)
        assert token.count(".") == 2
        from agentconnect.core.identity import verify_membership_attestation

        claims = verify_membership_attestation(token, team_did=team.team_did)
        assert claims["agent_did"] == writer.did
        assert claims["address"] == "writer@content-squad"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_sender_field_on_send_is_invalid_request(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    with pytest.raises(TeamError) as exc:
        await team.send(
            researcher["session_token"],
            {
                "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
                "recipient": "writer",
                "kind": "event",
                "content": "hello",
                "sender": writer["address"],
            },
        )
    assert exc.value.code == "invalid_request"
