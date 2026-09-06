"""Persisted Agent identity keeps the same DID across process restarts."""

from __future__ import annotations

import json

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.agent.identity import (
    load_identity,
    load_or_create_identity,
    save_identity,
)
from agentconnect.core.identity import AgentIdentity
from tests.agent.conftest import EchoAgent


def test_identity_path_reuses_the_saved_did(tmp_path):
    path = tmp_path / "researcher.json"
    first = EchoAgent(name="researcher", identity_path=path)
    second = EchoAgent(name="researcher", identity_path=path)
    assert second.agent_did == first.agent_did
    loaded = load_identity(path)
    assert loaded.did == first.agent_did


def test_identity_and_identity_path_cannot_be_combined(tmp_path):
    identity = AgentIdentity.create_key_based()
    with pytest.raises(ValueError, match="identity or identity_path"):
        BaseAgent(
            name="researcher",
            identity=identity,
            identity_path=tmp_path / "researcher.json",
        )


def test_load_or_create_identity_keeps_the_same_did(tmp_path):
    path = tmp_path / "researcher.json"
    first = load_or_create_identity(path)
    second = load_or_create_identity(path)
    assert second.did == first.did
    assert second.private_key == first.private_key


def test_save_and_load_identity_round_trip(tmp_path):
    path = tmp_path / "researcher.json"
    identity = AgentIdentity.create_key_based()
    save_identity(identity, path)
    loaded = load_identity(path)
    assert loaded.did == identity.did
    assert loaded.private_key == identity.private_key


def test_load_identity_rejects_a_file_without_a_private_key(tmp_path):
    path = tmp_path / "public-only.json"
    identity = AgentIdentity.create_key_based()
    path.write_text(json.dumps(identity.to_dict()), encoding="utf-8")
    with pytest.raises(ValueError, match="private key"):
        load_identity(path)
