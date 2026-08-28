"""Join, leave, reconnect, and discovery through BaseAgent."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.agent import BaseAgent, SessionError
from agentconnect.team import Team
from tests.agent.conftest import EchoAgent


@pytest.mark.asyncio
async def test_join_assigns_address_and_generated_instance_id(team: Team):
    writer = EchoAgent(name="writer")
    await writer.join(team)
    try:
        assert writer.address == "writer@content-squad"
        assert writer.connected
        uuid.UUID(writer.instance_id)
    finally:
        await writer.leave()


@pytest.mark.asyncio
async def test_supplied_instance_id_is_reused_on_rejoin(team: Team):
    instance = str(uuid.uuid4())
    first = EchoAgent(name="writer", instance_id=instance)
    await first.join(team)
    token = first._session.session_token
    await first.leave()
    second = EchoAgent(name="writer", instance_id=instance, identity=first.identity)
    await second.join(team)
    try:
        assert second.instance_id == instance
        assert second._session.session_token != token
    finally:
        await second.leave()


@pytest.mark.asyncio
async def test_leave_keeps_mailbox_for_later_join(team: Team):
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    await writer.leave()
    sent = await researcher.tell("writer", "queued while offline")
    assert sent["status"] == "accepted"
    await writer.join(team)
    try:
        result = await researcher.ask("writer", "hello", deadline_seconds=5)
        assert result["ticket"]["state"] == "completed"
        assert result["ticket"]["response"]["content"] == {"echo": "hello"}
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_join_retries_until_team_starts():
    runtime = Team("content-squad", session_ttl_seconds=30)
    writer = EchoAgent(name="writer")
    task = asyncio.create_task(writer.join(runtime))
    await asyncio.sleep(0.15)
    assert not task.done()
    await runtime.start()
    try:
        await asyncio.wait_for(task, timeout=5)
        assert writer.connected
    finally:
        await writer.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_and_get_profile(team: Team):
    writer = EchoAgent(
        name="writer",
        profile={
            "summary": "Writes short drafts from notes.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Turn notes into a two-paragraph draft.",
                }
            ],
            "tags": ["writing"],
        },
    )
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        found = await researcher.find("drafting")
        addresses = [match["address"] for match in found["matches"]]
        assert "writer@content-squad" in addresses
        assert "researcher@content-squad" not in addresses
        entry = await researcher.get_profile("writer")
        assert entry["address"] == "writer@content-squad"
        assert entry["profile"]["skills"][0]["name"] == "drafting"
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_ask_without_join_raises():
    agent = EchoAgent(name="lonely")
    with pytest.raises(SessionError) as exc:
        await agent.ask("writer", "hi")
    assert exc.value.code == "unauthorized"


@pytest.mark.asyncio
async def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        BaseAgent(name="not a name")
