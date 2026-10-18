"""Hosted Team construction used by ``agentconnect up``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.cli.hosting import (
    construct_hosted_agent,
    ensure_import_path,
    import_symbol,
    team_from_config,
)
from agentconnect.config.models import HostedAgentConfig, TeamConfig
from agentconnect.team import Team


class Echo(BaseAgent):
    """Hosted Agent used to prove construction and join."""

    profile = {
        "summary": "Echoes a request.",
        "skills": [
            {
                "name": "echo",
                "description": "Return the request content.",
            }
        ],
    }

    async def handle(self, msg, ctx: Any) -> Any:
        if msg.kind != "request":
            return None
        return msg.content


def _spec(entrypoint: str, **kwargs: Any) -> HostedAgentConfig:
    return HostedAgentConfig(entrypoint=entrypoint, kwargs=dict(kwargs))


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


def test_construct_class_and_factory() -> None:
    classed = construct_hosted_agent("echo", _spec(f"{__name__}:Echo"))
    assert isinstance(classed, Echo)
    assert classed.name == "echo"

    def create_echo(name: str) -> BaseAgent:
        return Echo(name=name)

    globals()["create_echo"] = create_echo
    built = construct_hosted_agent("echo", _spec(f"{__name__}:create_echo"))
    assert isinstance(built, Echo)
    assert built.name == "echo"


def test_construct_forwards_kwargs() -> None:
    seen: dict[str, object] = {}

    def create_echo(name: str, model: str) -> BaseAgent:
        seen["model"] = model
        return Echo(name=name)

    globals()["create_echo_kwargs"] = create_echo
    built = construct_hosted_agent(
        "echo", _spec(f"{__name__}:create_echo_kwargs", model="provider/model")
    )
    assert isinstance(built, Echo)
    assert seen["model"] == "provider/model"


@pytest.mark.asyncio
async def test_construct_rejects_joined_agent_without_leaving() -> None:
    team = await Team("demo-team", require_join_auth=False, embeddings="none").start()
    agent = Echo(name="echo")
    try:
        await agent.join(team)
        assert agent.connected

        def already_joined(name: str) -> BaseAgent:
            return agent

        globals()["already_joined"] = already_joined
        with pytest.raises(ValueError, match="joined Agent"):
            construct_hosted_agent("echo", _spec(f"{__name__}:already_joined"))
        assert agent.connected
    finally:
        await agent.leave()
        await team.stop()


def test_construct_rejects_async_factory_without_leaking() -> None:
    async def async_create(name: str) -> BaseAgent:
        return Echo(name=name)

    globals()["async_create"] = async_create
    with pytest.raises(ValueError, match="synchronous"):
        construct_hosted_agent("echo", _spec(f"{__name__}:async_create"))


def test_construct_closes_returned_coroutine() -> None:
    import inspect

    held: list[object] = []

    def returns_coro(name: str):
        async def _inner() -> BaseAgent:
            return Echo(name=name)

        coro = _inner()
        held.append(coro)
        return coro

    globals()["returns_coro"] = returns_coro
    with pytest.raises(ValueError, match="coroutine"):
        construct_hosted_agent("echo", _spec(f"{__name__}:returns_coro"))
    assert inspect.getcoroutinestate(held[0]) == inspect.CORO_CLOSED


def test_construct_wraps_ordinary_factory_errors() -> None:
    def boom(name: str) -> BaseAgent:
        raise RuntimeError("model setup failed")

    globals()["boom"] = boom
    with pytest.raises(ValueError, match="model setup failed"):
        construct_hosted_agent("echo", _spec(f"{__name__}:boom"))


def test_construct_preserves_typeerror_cause() -> None:
    def no_kwargs(name: str) -> BaseAgent:
        return Echo(name=name)

    globals()["no_kwargs"] = no_kwargs
    with pytest.raises(ValueError, match="could not construct 'echo' from") as caught:
        construct_hosted_agent(
            "echo", _spec(f"{__name__}:no_kwargs", model="provider/model")
        )
    assert "model" in str(caught.value)
    assert isinstance(caught.value.__cause__, TypeError)


def test_construct_rejects_non_agent_and_wrong_name() -> None:
    def not_an_agent(name: str) -> str:
        return name

    def wrong_name(name: str) -> BaseAgent:
        return Echo(name="other")

    globals()["not_an_agent"] = not_an_agent
    globals()["wrong_name"] = wrong_name
    with pytest.raises(ValueError, match="not a BaseAgent"):
        construct_hosted_agent("echo", _spec(f"{__name__}:not_an_agent"))
    with pytest.raises(ValueError, match="expected 'echo'"):
        construct_hosted_agent("echo", _spec(f"{__name__}:wrong_name"))


def test_selected_project_imports_beat_cwd_and_nested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    project = tmp_path / "project"
    unrelated = tmp_path / "unrelated"
    nested = project / "nested"
    for directory in (project, unrelated, nested):
        (directory / "m11probe").mkdir(parents=True)
    (project / "m11probe" / "__init__.py").write_text(
        "SOURCE = 'project'\n", encoding="utf-8"
    )
    (unrelated / "m11probe" / "__init__.py").write_text(
        "SOURCE = 'cwd'\n", encoding="utf-8"
    )
    (nested / "m11probe" / "__init__.py").write_text(
        "SOURCE = 'nested'\n", encoding="utf-8"
    )
    saved_path = list(sys.path)
    sys.modules.pop("m11probe", None)
    try:
        monkeypatch.chdir(unrelated)
        sys.path.insert(0, str(unrelated.resolve()))
        sys.path.append(str(project.resolve()))
        ensure_import_path(project)
        import m11probe

        assert m11probe.SOURCE == "project"

        sys.modules.pop("m11probe", None)
        monkeypatch.chdir(nested)
        sys.path.insert(0, str(nested.resolve()))
        ensure_import_path(project)
        import m11probe as nested_probe

        assert nested_probe.SOURCE == "project"
    finally:
        sys.modules.pop("m11probe", None)
        sys.path[:] = saved_path
