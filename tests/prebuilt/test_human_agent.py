"""HumanAgent stdin replies."""

from __future__ import annotations

from typing import Any

import pytest

from agentconnect.prebuilt import HumanAgent
from agentconnect.team import Team


@pytest.mark.asyncio
async def test_human_process_message_returns_typed_text():
    async def fake_input(prompt: str = "") -> str:
        return "hello from human"

    human = HumanAgent(name="operator-human", read_line=fake_input)
    reply = await human.process_message(
        {"sender": "assistant@content-squad", "content": "Are you there?"}
    )
    assert reply == "hello from human"


@pytest.mark.asyncio
async def test_human_empty_input_declines():
    async def fake_input(prompt: str = "") -> str:
        return "   "

    human = HumanAgent(name="operator-human", read_line=fake_input)
    assert await human.process_message({"sender": "a", "content": "hi"}) is None


@pytest.mark.asyncio
async def test_human_exit_declines():
    async def fake_input(prompt: str = "") -> str:
        return "exit"

    human = HumanAgent(name="operator-human", read_line=fake_input)
    assert await human.process_message({"sender": "a", "content": "hi"}) is None


@pytest.mark.asyncio
async def test_human_joins_team_and_replies():
    async def fake_input(prompt: str = "") -> str:
        return "noted"

    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human", read_line=fake_input)

    from agentconnect.agent import BaseAgent

    class Peer(BaseAgent):
        async def process_message(self, message: dict[str, Any], ctx) -> Any:
            return None

    peer = Peer(name="asker")
    await human.join(team)
    await peer.join(team)
    try:
        result = await peer.ask("operator-human", "please confirm")
        assert result["ticket"]["state"] == "completed"
        assert result["ticket"]["response"]["content"] == "noted"
    finally:
        await peer.leave()
        await human.leave()
        await team.stop()
