"""Ed25519 did:key, identity proofs, and membership attestations."""

from __future__ import annotations

from datetime import timedelta

import pytest

from agentconnect.core.identity import (
    AgentIdentity,
    did_key_from_public_bytes,
    encode_eddsa_jwt,
    issue_identity_proof,
    issue_membership_attestation,
    public_bytes_from_did_key,
    utc_now,
    verify_identity_proof,
    verify_membership_attestation,
)


def test_create_key_based_round_trips_did_key():
    identity = AgentIdentity.create_key_based()
    assert identity.did.startswith("did:key:z")
    assert identity.matches_did()
    assert public_bytes_from_did_key(identity.did) == identity.public_bytes()
    restored = did_key_from_public_bytes(identity.public_bytes())
    assert restored == identity.did


def test_sign_and_verify_message():
    identity = AgentIdentity.create_key_based()
    other = AgentIdentity.create_key_based()
    signature = identity.sign_message("hello")
    assert identity.verify_signature("hello", signature)
    assert not other.verify_signature("hello", signature)


def test_identity_proof_round_trip():
    identity = AgentIdentity.create_key_based()
    expires = utc_now() + timedelta(seconds=60)
    challenge = {
        "nonce": "Up7Zu1q56kN6VfGqUZqffA",
        "audience": "agentconnect:content-squad",
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    proof = issue_identity_proof(identity, challenge)
    payload = verify_identity_proof(proof, agent_did=identity.did, challenge=challenge)
    assert payload["iss"] == identity.did
    assert payload["aud"] == challenge["audience"]
    assert payload["nonce"] == challenge["nonce"]


def test_identity_proof_rejects_wrong_key():
    identity = AgentIdentity.create_key_based()
    other = AgentIdentity.create_key_based()
    expires = utc_now() + timedelta(seconds=60)
    challenge = {
        "nonce": "Up7Zu1q56kN6VfGqUZqffA",
        "audience": "agentconnect:content-squad",
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    proof = issue_identity_proof(other, challenge)
    with pytest.raises(ValueError):
        verify_identity_proof(proof, agent_did=identity.did, challenge=challenge)


def test_identity_proof_rejects_expired_exp():
    identity = AgentIdentity.create_key_based()
    expires = utc_now() + timedelta(seconds=60)
    challenge = {
        "nonce": "Up7Zu1q56kN6VfGqUZqffA",
        "audience": "agentconnect:content-squad",
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    now = int(utc_now().timestamp())
    token = encode_eddsa_jwt(
        {
            "iss": identity.did,
            "aud": challenge["audience"],
            "nonce": challenge["nonce"],
            "iat": now - 120,
            "exp": now - 60,
        },
        identity.private_key,
    )
    with pytest.raises(ValueError):
        verify_identity_proof(token, agent_did=identity.did, challenge=challenge)


def test_membership_attestation_round_trip():
    team = AgentIdentity.create_key_based()
    agent = AgentIdentity.create_key_based()
    token = issue_membership_attestation(
        team,
        agent_did=agent.did,
        name="writer",
        address="writer@content-squad",
        team_name="content-squad",
    )
    claims = verify_membership_attestation(token, team_did=team.did)
    assert claims["agent_did"] == agent.did
    assert claims["name"] == "writer"
    assert claims["address"] == "writer@content-squad"
    assert claims["team_name"] == "content-squad"
