"""HumanAgent stdin replies."""

from __future__ import annotations

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.agent.context import Context
from agentconnect.core.base import JsonValue
from agentconnect.core.message import MailboxMessage
from agentconnect.prebuilt import HumanAgent
from agentconnect.team import Team


@pytest.mark.asyncio
async def test_human_empty_input_declines():
    async def fake_input(prompt: str = "") -> str:
        return "   "

    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human", read_line=fake_input)

    class Peer(BaseAgent):
        async def handle(self, message: MailboxMessage, ctx: Context) -> JsonValue:
            return None

    peer = Peer(name="asker")
    await human.join(team)
    await peer.join(team)
    try:
        result = await peer.ask("operator-human", "hi")
        assert result.state == "declined"
    finally:
        await peer.leave()
        await human.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_human_exit_declines():
    async def fake_input(prompt: str = "") -> str:
        return "exit"

    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human", read_line=fake_input)

    class Peer(BaseAgent):
        async def handle(self, message: MailboxMessage, ctx: Context) -> JsonValue:
            return None

    peer = Peer(name="asker")
    await human.join(team)
    await peer.join(team)
    try:
        result = await peer.ask("operator-human", "hi")
        assert result.state == "declined"
    finally:
        await peer.leave()
        await human.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_human_joins_team_and_replies():
    async def fake_input(prompt: str = "") -> str:
        return "noted"

    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human", read_line=fake_input)

    class Peer(BaseAgent):
        async def handle(self, message: MailboxMessage, ctx: Context) -> JsonValue:
            return None

    peer = Peer(name="asker")
    await human.join(team)
    await peer.join(team)
    try:
        result = await peer.ask("operator-human", "please confirm")
        assert result.state == "completed"
        assert result.response.content == "noted"
    finally:
        await peer.leave()
        await human.leave()
        await team.stop()
