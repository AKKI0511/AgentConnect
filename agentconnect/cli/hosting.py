"""Load a symbol from a ``module:Name`` reference and construct hosted Agents."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from collections.abc import Callable

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


def import_symbol(ref: str) -> object:
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


def construct_hosted_agent(name: str, spec: HostedAgentConfig) -> BaseAgent:
    """Build an unjoined Agent from a Team-file ``entrypoint``.

    ``entrypoint`` is a ``BaseAgent`` subclass or a synchronous factory.
    Both are called as ``target(name=name, **kwargs)``. The result must be
    an unjoined ``BaseAgent`` whose ``name`` matches ``name``.
    """
    target = import_symbol(spec.entrypoint)
    if inspect.iscoroutinefunction(target) or inspect.isasyncgenfunction(target):
        raise ValueError(
            f"{spec.entrypoint} must be synchronous; create(name, **kwargs) "
            "cannot be async"
        )
    if not callable(target):
        raise ValueError(
            f"{spec.entrypoint} must be a BaseAgent subclass or a function "
            "create(name, **kwargs) that returns an unjoined BaseAgent"
        )
    try:
        agent = target(name=name, **dict(spec.kwargs))
    except TypeError as exc:
        raise ValueError(
            f"could not construct {name!r} from {spec.entrypoint}: {exc}"
        ) from exc
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise ValueError(f"{spec.entrypoint}: {exc}") from exc
    if inspect.iscoroutine(agent):
        agent.close()
        raise ValueError(
            f"{spec.entrypoint} must be synchronous; create(name, **kwargs) "
            "returned a coroutine"
        )
    if not isinstance(agent, BaseAgent):
        raise ValueError(
            f"{spec.entrypoint} returned {type(agent).__name__}, not a BaseAgent"
        )
    if getattr(agent, "_session", None) is not None:
        raise ValueError(
            f"{spec.entrypoint} returned a joined Agent; create(name, **kwargs) "
            "must return an unjoined BaseAgent"
        )
    if agent.name != name:
        raise ValueError(
            f"{spec.entrypoint} built Agent {agent.name!r}, expected {name!r}"
        )
    return agent


def _is_control_flow(exc: BaseException) -> bool:
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        return True
    return type(exc).__name__ == "CancelledError"


def team_from_config(config: TeamConfig) -> Team:
    """Build an unstarted Team from a Team file."""
    extras: list[Callable[..., object]] = []
    for ref in config.tools:
        try:
            symbol = import_symbol(ref)
            if not callable(symbol):
                raise ValueError(f"{ref} is not callable")
            extras.append(symbol)
        except Exception as exc:
            raise ValueError(f"could not import extra tool {ref}: {exc}") from exc
    return Team(
        config.team,
        store=config.store,
        embeddings=config.embeddings,
        tools=extras or None,
        require_join_auth=config.require_join_auth,
    )
