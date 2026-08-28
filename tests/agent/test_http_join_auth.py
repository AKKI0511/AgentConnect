"""Authenticated HTTP join: token binding and Session drop."""

from __future__ import annotations

import pytest

from agentconnect.agent import SessionError
from agentconnect.core.identity import AgentIdentity
from agentconnect.team import Team
from tests.agent.conftest import EchoAgent


@pytest.mark.asyncio
async def test_http_join_with_bound_token():
    team = await Team("content-squad", require_join_auth=True).start()
    writer_id = AgentIdentity.create_key_based()
    researcher_id = AgentIdentity.create_key_based()
    writer = EchoAgent(name="writer", identity=writer_id)
    researcher = EchoAgent(name="researcher", identity=researcher_id)
    try:
        url = await team.serve()
        writer_tok = await team.issue_join_token(
            name="writer", agent_did=writer.agent_did
        )
        researcher_tok = await team.issue_join_token(
            name="researcher", agent_did=researcher.agent_did
        )
        await writer.join(url, join_token=writer_tok["token"])
        await researcher.join(url, join_token=researcher_tok["token"])
        result = await researcher.ask("writer", "hello", deadline_seconds=8)
        assert result["ticket"]["state"] == "completed"
        assert result["ticket"]["response"]["content"] == {"echo": "hello"}
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_http_join_rejects_stolen_did_bound_token():
    team = await Team("content-squad", require_join_auth=True).start()
    writer_id = AgentIdentity.create_key_based()
    thief_id = AgentIdentity.create_key_based()
    writer = EchoAgent(name="writer", identity=writer_id)
    thief = EchoAgent(name="writer", identity=thief_id)
    try:
        url = await team.serve()
        issued = await team.issue_join_token(name="writer", agent_did=writer.agent_did)
        with pytest.raises(SessionError) as exc:
            await thief.join(url, join_token=issued["token"])
        assert exc.value.code == "unauthorized"
        assert thief.address is None
        await writer.join(url, join_token=issued["token"])
        assert writer.address == "writer@content-squad"
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_http_loopback_join_without_token_still_proves_did():
    team = await Team("content-squad").start()
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve()
        await writer.join(url)
        await researcher.join(url)
        result = await researcher.ask("writer", "via-http", deadline_seconds=8)
        assert result["ticket"]["state"] == "completed"
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()
