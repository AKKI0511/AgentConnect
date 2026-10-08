"""Load a symbol from a ``module:Name`` reference and join hosted Agents."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

from agentconnect.agent.base import BaseAgent
from agentconnect.config.models import HostedAgentConfig, TeamConfig
from agentconnect.team.runtime import Team


def ensure_import_path(directory: Path) -> None:
    """Put ``directory`` first on ``sys.path`` so its modules win over cwd.

    Args:
        directory: Directory of the selected Team file. Hosted Agents and
            extra tools are imported from here.
    """
    resolved = str(directory.resolve())
    sys.path[:] = [entry for entry in sys.path if entry != resolved]
    sys.path.insert(0, resolved)


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


def construct_hosted_agent(spec: HostedAgentConfig) -> BaseAgent:
    """Build an unjoined Agent from a Team-file ``class`` entry.

    ``class`` is a ``BaseAgent`` subclass, or a function
    ``create(name) -> BaseAgent``. The result must be an unjoined
    ``BaseAgent`` whose ``name`` matches the file.
    """
    target = import_symbol(spec.class_path)
    if inspect.iscoroutinefunction(target) or inspect.isasyncgenfunction(target):
        raise ValueError(
            f"{spec.class_path} must be synchronous; create(name) cannot be async"
        )
    if not callable(target):
        raise ValueError(
            f"{spec.class_path} must be a BaseAgent subclass or a function "
            "create(name) that returns an unjoined BaseAgent"
        )
    try:
        agent = target(name=spec.name)
    except TypeError as exc:
        raise ValueError(
            f"{spec.class_path} must accept name={spec.name!r} and return an "
            f"unjoined BaseAgent ({exc})"
        ) from exc
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise ValueError(f"{spec.class_path}: {exc}") from exc
    if inspect.iscoroutine(agent):
        agent.close()
        raise ValueError(
            f"{spec.class_path} must be synchronous; create(name) returned a coroutine"
        )
    if not isinstance(agent, BaseAgent):
        raise ValueError(
            f"{spec.class_path} returned {type(agent).__name__}, not a BaseAgent"
        )
    if getattr(agent, "_session", None) is not None:
        raise ValueError(
            f"{spec.class_path} returned a joined Agent; create(name) must "
            "return an unjoined BaseAgent"
        )
    if agent.name != spec.name:
        raise ValueError(
            f"{spec.class_path} built Agent {agent.name!r}, expected {spec.name!r}"
        )
    return agent


def _is_control_flow(exc: BaseException) -> bool:
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        return True
    return type(exc).__name__ == "CancelledError"


def team_from_config(config: TeamConfig) -> Team:
    """Build an unstarted Team from a Team file."""
    extras: list[Any] = []
    for ref in config.tools:
        try:
            extras.append(import_symbol(ref))
        except Exception as exc:
            raise ValueError(f"could not import extra tool {ref}: {exc}") from exc
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
