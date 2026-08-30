"""Load a symbol from a ``module:Name`` reference and join hosted Agents."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from agentconnect.config.models import TeamConfig
from agentconnect.team.runtime import Team


def ensure_cwd_on_path(root: Path | None = None) -> None:
    """Put the project directory on ``sys.path`` so hosted classes import."""
    directory = str((root or Path.cwd()).resolve())
    if directory not in sys.path:
        sys.path.insert(0, directory)


def import_symbol(ref: str) -> Any:
    """Import ``module:attr`` and return the attribute.

    Writer = import_symbol("agents.writer:Writer")
    """
    module_name, sep, attr = ref.rpartition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"import path must be module:Name, got {ref!r}")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise ValueError(f"{ref} was not found") from exc


def team_from_config(config: TeamConfig) -> Team:
    """Build an unstarted Team from a Team file."""
    extras = [import_symbol(ref) for ref in config.tools]
    return Team(
        config.team,
        store=config.store,
        embeddings=config.embeddings,
        tools=extras or None,
        require_join_auth=config.require_join_auth,
    )


async def join_hosted_agent(team: Team, agent: Any) -> None:
    """Join ``agent`` to ``team``, issuing a token when the Team requires auth."""
    if team.require_join_auth:
        issued = await team.issue_join_token(name=agent.name, agent_did=agent.agent_did)
        await agent.join(team, join_token=issued["token"])
        return
    await agent.join(team)
