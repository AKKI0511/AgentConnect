"""Hosted Team construction used by ``agentconnect up``."""

from __future__ import annotations

from typing import Any

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.cli.hosting import (
    import_symbol,
    join_hosted_agent,
    team_from_config,
)
from agentconnect.config.models import TeamConfig
from agentconnect.team import Team


class Echo(BaseAgent):
    """Hosted Agent used to prove ``join_hosted_agent`` opens a Membership."""

    profile = {
        "summary": "Echoes a request.",
        "skills": [
            {
                "name": "echo",
                "description": "Return the request content.",
            }
        ],
    }

    async def process_message(self, msg: dict[str, Any], ctx: Any) -> Any:
        if msg.get("kind") != "request":
            return None
        return msg.get("content")


def test_import_symbol_and_team_from_config() -> None:
    loaded = import_symbol("agentconnect.team.errors:TeamError")
    from agentconnect.team.errors import TeamError

    assert loaded is TeamError
    with pytest.raises(ValueError):
        import_symbol("not-a-path")
    config = TeamConfig(
        team="demo-team",
        store="memory",
        embeddings="none",
        require_join_auth=True,
    )
    team = team_from_config(config)
    assert team.name == "demo-team"
    assert team.require_join_auth is True


@pytest.mark.asyncio
async def test_join_hosted_agent_issues_token() -> None:
    team = await Team("demo-team", require_join_auth=True, embeddings="none").start()
    agent = Echo(name="echo")
    try:
        await join_hosted_agent(team, agent)
        operator = await team.ensure_operator_session()
        snapshot = await team.status(operator)
        names = {row["name"] for row in snapshot["members"]}
        assert "echo" in names
    finally:
        await agent.leave()
        await team.stop()
