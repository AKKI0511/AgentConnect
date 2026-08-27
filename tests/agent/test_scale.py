"""Many independent BaseAgents join, talk, leave, and rejoin."""

from __future__ import annotations

import asyncio

import pytest

from agentconnect.team import Team
from tests.agent.conftest import EchoAgent


@pytest.mark.asyncio
async def test_many_agents_join_talk_and_leave(team: Team):
    n = 24
    agents = [EchoAgent(name=f"agent{i:02d}", max_in_flight=2) for i in range(n)]
    await asyncio.gather(*(agent.join(team) for agent in agents))
    try:
        pairs = [
            agents[i].ask(
                agents[i + 1].name,
                {"n": i},
                deadline_seconds=10,
                collect="wait",
            )
            for i in range(0, n, 2)
        ]
        results = await asyncio.gather(*pairs)
        for i, result in enumerate(results):
            assert result["ticket"]["state"] == "completed"
            assert result["ticket"]["response"]["content"] == {"echo": {"n": i * 2}}

        leaving = agents[:8]
        await asyncio.gather(*(agent.leave() for agent in leaving))
        remaining = agents[8:]
        still = remaining[0].ask(remaining[1].name, "still-here", deadline_seconds=8)
        result = await still
        assert result["ticket"]["state"] == "completed"

        await asyncio.gather(*(agent.join(team) for agent in leaving))
        back = leaving[0].ask(leaving[1].name, "back", deadline_seconds=8)
        result = await back
        assert result["ticket"]["state"] == "completed"
    finally:
        await asyncio.gather(
            *(agent.leave() for agent in agents), return_exceptions=True
        )


@pytest.mark.asyncio
async def test_dynamic_join_mid_conversation(team: Team):
    a = EchoAgent(name="alpha")
    b = EchoAgent(name="beta")
    await a.join(team)
    await b.join(team)
    try:
        first = await a.ask("beta", "one", deadline_seconds=5)
        assert first["ticket"]["state"] == "completed"
        gamma = EchoAgent(name="gamma")
        await gamma.join(team)
        second = await gamma.ask("alpha", "two", deadline_seconds=5)
        assert second["ticket"]["state"] == "completed"
        await gamma.leave()
        third = await b.ask("alpha", "three", deadline_seconds=5)
        assert third["ticket"]["state"] == "completed"
    finally:
        await a.leave()
        await b.leave()
