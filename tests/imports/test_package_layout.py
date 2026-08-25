"""Import-boundary checks for the Team-based package layout."""

import importlib
import sys
from collections.abc import Iterable

import pytest


def _names_with_prefix(prefix: str) -> list[str]:
    return [
        name for name in sys.modules if name == prefix or name.startswith(prefix + ".")
    ]


def _pop_modules(names: Iterable[str]) -> dict[str, object]:
    saved: dict[str, object] = {}
    for name in names:
        module = sys.modules.pop(name, None)
        if module is not None:
            saved[name] = module
    return saved


def _restore_modules(saved: dict[str, object]) -> None:
    sys.modules.update(saved)
    for name, module in saved.items():
        parent_name, _, attr = name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None and attr:
            setattr(parent, attr, module)


def test_team_runtime_does_not_load_agent_package():
    saved_agent = _pop_modules(_names_with_prefix("agentconnect.agent"))
    saved_runtime = _pop_modules(_names_with_prefix("agentconnect.team.runtime"))
    try:
        importlib.import_module("agentconnect.team.runtime")
        loaded = _names_with_prefix("agentconnect.agent")
        assert loaded == []
    finally:
        _restore_modules(saved_runtime)
        _restore_modules(saved_agent)


def test_agent_base_does_not_load_team_package():
    saved_team = _pop_modules(_names_with_prefix("agentconnect.team"))
    saved_base = _pop_modules(_names_with_prefix("agentconnect.agent.base"))
    try:
        importlib.import_module("agentconnect.agent.base")
        loaded = _names_with_prefix("agentconnect.team")
        assert loaded == []
    finally:
        _restore_modules(saved_base)
        _restore_modules(saved_team)


def test_core_does_not_export_base_agent():
    import agentconnect.core as core

    assert "BaseAgent" not in core.__all__
    with pytest.raises(ImportError):
        from agentconnect.core import BaseAgent  # noqa: F401
