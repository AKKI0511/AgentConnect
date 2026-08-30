"""Session-bound Team tools for hosts that do not speak MCP."""

from __future__ import annotations

from typing import Any

import pytest

from agentconnect.agent import BaseAgent, SessionError, TeamTools
from agentconnect.team import Team


class Writer(BaseAgent):
    """Echoes reply-expected work."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn research notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def process_message(self, message: dict[str, Any], ctx) -> Any:
        if message.get("kind") == "request" and message.get("deadline"):
            return {"echo": message.get("content")}
        return None


class Coordinator(BaseAgent):
    """Finds a teammate through tools, then asks that teammate to work."""

    profile = {
        "summary": "Finds teammates and hires them for specialized work.",
        "skills": [
            {
                "name": "research",
                "description": "Find sources and decide who should handle a task.",
            }
        ],
        "tags": ["research"],
    }

    def __init__(self, name: str):
        super().__init__(name=name)
        self.tools = self.team_tools()

    async def process_message(self, message: dict[str, Any], ctx) -> Any:
        return None


@pytest.mark.asyncio
async def test_team_tools_before_join_fail_on_call():
    agent = Coordinator(name="researcher")
    assert isinstance(agent.tools, TeamTools)
    assert [item.name for item in agent.tools] == [
        "find",
        "ask",
        "tell",
        "get_result",
        "get_history",
    ]
    with pytest.raises(SessionError) as exc:
        await agent.tools.find(query="someone who can draft a summary")
    assert exc.value.code == "unauthorized"


@pytest.mark.asyncio
async def test_team_tools_find_then_ask_without_hardcoded_address():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Coordinator(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        found = await researcher.tools.find(query="someone who can draft a summary")
        recipient = next(
            match["address"]
            for match in found["matches"]
            if match["address"].startswith("writer@")
        )
        ticket = await researcher.tools.ask(
            recipient=recipient,
            content="draft this",
            deadline_seconds=30,
            wait_seconds=8,
        )
        assert ticket["state"] == "completed"
        assert ticket["response"]["content"] == {"echo": "draft this"}
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_team_tools_idempotency_key_reuses_ticket():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Coordinator(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        first = await researcher.tools.ask(
            recipient="writer",
            content="same",
            deadline_seconds=30,
            wait_seconds=8,
            idempotency_key="draft-1",
        )
        second = await researcher.tools.ask(
            recipient="writer",
            content="same",
            deadline_seconds=30,
            wait_seconds=8,
            idempotency_key="draft-1",
        )
        third = await researcher.tools.ask(
            recipient="writer",
            content="same",
            deadline_seconds=30,
            wait_seconds=8,
        )
        assert first["id"] == second["id"]
        assert first["id"] != third["id"]
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()
