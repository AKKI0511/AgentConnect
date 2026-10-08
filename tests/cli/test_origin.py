"""CLI origin selection: --url, --file, saved state, then discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentconnect.cli.origin import DEFAULT_ORIGIN, resolve_runtime_origin
from agentconnect.cli.state import write_state
from agentconnect.config.loaders import dump_team_toml
from agentconnect.config.models import TeamConfig


def _toml(path: Path, *, team: str, port: int) -> Path:
    path.write_text(
        dump_team_toml(TeamConfig(team=team, port=port)),
        encoding="utf-8",
    )
    return path


def test_explicit_file_beats_saved_state(tmp_path: Path) -> None:
    stale = _toml(tmp_path / "agentconnect.toml", team="stale", port=9876)
    chosen = _toml(tmp_path / "other.toml", team="chosen", port=9877)
    write_state(
        stale,
        pid=1,
        url="http://127.0.0.1:9876",
        team="stale",
        created="test",
    )
    origin = resolve_runtime_origin(file=chosen, start=tmp_path)
    assert origin == "http://127.0.0.1:9877"


def test_url_beats_file_and_state(tmp_path: Path) -> None:
    chosen = _toml(tmp_path / "other.toml", team="chosen", port=9877)
    write_state(
        chosen,
        pid=1,
        url="http://127.0.0.1:9876",
        team="stale",
        created="test",
    )
    origin = resolve_runtime_origin(
        url="http://127.0.0.1:9555/",
        file=chosen,
        start=tmp_path,
    )
    assert origin == "http://127.0.0.1:9555"


def test_state_beats_discovered_file(tmp_path: Path) -> None:
    _toml(tmp_path / "agentconnect.toml", team="file-team", port=9001)
    write_state(
        tmp_path / "agentconnect.toml",
        pid=1,
        url="http://127.0.0.1:9876",
        team="running",
        created="test",
    )
    origin = resolve_runtime_origin(start=tmp_path)
    assert origin == "http://127.0.0.1:9876"


def test_missing_explicit_file_does_not_fall_back(tmp_path: Path) -> None:
    write_state(
        tmp_path / "agentconnect.toml",
        pid=1,
        url="http://127.0.0.1:9876",
        team="stale",
        created="test",
    )
    with pytest.raises(FileNotFoundError, match="not found"):
        resolve_runtime_origin(file=tmp_path / "missing.toml", start=tmp_path)


def test_invalid_explicit_file_does_not_fall_back(tmp_path: Path) -> None:
    write_state(
        tmp_path / "agentconnect.toml",
        pid=1,
        url="http://127.0.0.1:9876",
        team="stale",
        created="test",
    )
    broken = tmp_path / "broken.toml"
    broken.write_text("team = [\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid TOML"):
        resolve_runtime_origin(file=broken, start=tmp_path)


def test_default_origin_without_file_or_state(tmp_path: Path) -> None:
    assert resolve_runtime_origin(start=tmp_path) == DEFAULT_ORIGIN
