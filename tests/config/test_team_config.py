"""Team file models, TOML discovery, and the YAML compatibility path."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentconnect.config.loaders import (
    dump_team_toml,
    find_config_file,
    load_team_config,
    render_example_toml,
    save_example_config,
    validate_config_file,
)
from agentconnect.config.models import HostedAgentConfig, TeamConfig


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_example_toml_matches_models() -> None:
    committed = Path("agentconnect/config/agentconnect.example.toml").read_text(
        encoding="utf-8"
    )
    assert committed.replace("\r\n", "\n") == render_example_toml().replace(
        "\r\n", "\n"
    )
    parsed = load_team_config(Path("agentconnect/config/agentconnect.example.toml"))
    assert parsed.model_dump(by_alias=True) == TeamConfig.example().model_dump(
        by_alias=True
    )


def test_load_team_config_from_cwd_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    save_example_config(tmp_path / "agentconnect.toml")
    config = load_team_config()
    assert config.team == "content-squad"
    assert config.agents[0].class_path.startswith("agents.")
    assert find_config_file() == tmp_path / "agentconnect.toml"


def test_load_pyproject_tool_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "pyproject.toml",
        dump_team_toml(TeamConfig(team="from-pyproject")),
    )
    config = load_team_config()
    assert config.team == "from-pyproject"
    assert find_config_file() == tmp_path / "pyproject.toml"


def test_toml_beats_pyproject_in_same_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "agentconnect.toml", dump_team_toml(TeamConfig(team="from-toml")))
    _write(
        tmp_path / "pyproject.toml",
        dump_team_toml(TeamConfig(team="from-pyproject")),
    )
    assert load_team_config().team == "from-toml"
    assert find_config_file() == tmp_path / "agentconnect.toml"


def test_pyproject_in_parent_beats_cwd_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml = pytest.importorskip("yaml")
    project = tmp_path / "project"
    nested = project / "nested"
    nested.mkdir(parents=True)
    _write(project / "pyproject.toml", dump_team_toml(TeamConfig(team="from-parent")))
    _write(
        nested / "agentconnect.yaml",
        yaml.safe_dump({"team": "from-yaml"}),
    )
    monkeypatch.chdir(nested)
    assert load_team_config().team == "from-parent"
    assert find_config_file() == project / "pyproject.toml"


def test_yaml_fallback_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml = pytest.importorskip("yaml")
    monkeypatch.chdir(tmp_path)
    path = _write(
        tmp_path / "agentconnect.yaml",
        yaml.safe_dump({"team": "legacy-yaml", "store": "memory"}),
    )
    with pytest.warns(DeprecationWarning, match="legacy YAML"):
        config = load_team_config()
    assert config.team == "legacy-yaml"
    assert find_config_file() == path


def test_explicit_file_skips_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    _write(other / "agentconnect.toml", dump_team_toml(TeamConfig(team="cwd-team")))
    chosen = _write(
        tmp_path / "custom.toml",
        dump_team_toml(TeamConfig(team="explicit-team")),
    )
    assert load_team_config(chosen).team == "explicit-team"


def test_agentconnect_toml_accepts_bare_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "agentconnect.toml",
        'team = "bare-keys"\nstore = "memory"\n',
    )
    assert load_team_config().team == "bare-keys"


def test_malformed_toml_is_an_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "agentconnect.toml", "team = [unterminated\n")
    with pytest.raises(ValueError, match="invalid TOML"):
        load_team_config(path)


def test_pyproject_without_table_is_not_a_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "pyproject.toml", '[project]\nname = "demo"\n')
    with pytest.raises(FileNotFoundError, match="Team file was not found"):
        load_team_config()


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(Exception):
        TeamConfig.model_validate({"team": "content-squad", "publish": ["writer"]})


def test_store_and_embeddings_validation() -> None:
    TeamConfig.model_validate({"team": "demo", "store": "redis://localhost:6379/0"})
    TeamConfig.model_validate(
        {"team": "demo", "embeddings": "litellm:text-embedding-3-small"}
    )
    TeamConfig.model_validate({"team": "demo", "embeddings": "openai"})
    with pytest.raises(Exception):
        TeamConfig.model_validate({"team": "demo", "store": "postgres://x"})
    with pytest.raises(Exception):
        TeamConfig.model_validate({"team": "demo", "embeddings": "torch"})
    with pytest.raises(Exception):
        TeamConfig.model_validate({"team": "demo", "host": "0.0.0.0"})


def test_hosted_agent_class_path() -> None:
    agent = HostedAgentConfig.model_validate(
        {"class": "agents.writer:Writer", "name": "Writer"}
    )
    assert agent.name == "writer"
    assert agent.class_path == "agents.writer:Writer"
    with pytest.raises(Exception):
        HostedAgentConfig.model_validate({"class": "agents.writer", "name": "writer"})


def test_discovery_walks_beyond_sixteen_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path
    for index in range(20):
        nested = nested / f"d{index}"
    nested.mkdir(parents=True)
    chosen = _write(
        tmp_path / "agentconnect.toml", dump_team_toml(TeamConfig(team="from-root"))
    )
    monkeypatch.chdir(nested)
    assert load_team_config().team == "from-root"
    assert find_config_file() == chosen


def test_nearest_pyproject_beats_ancestor_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    nested = project / "nested"
    nested.mkdir(parents=True)
    _write(project / "agentconnect.toml", dump_team_toml(TeamConfig(team="ancestor")))
    _write(nested / "pyproject.toml", dump_team_toml(TeamConfig(team="nearest")))
    monkeypatch.chdir(nested)
    assert load_team_config().team == "nearest"
    assert find_config_file() == nested / "pyproject.toml"


def test_duplicate_agent_names_are_rejected() -> None:
    with pytest.raises(Exception, match="duplicate Agent name"):
        TeamConfig.model_validate(
            {
                "team": "demo",
                "agents": [
                    {"class": "agents.writer:Writer", "name": "writer"},
                    {"class": "agents.other:Other", "name": "writer"},
                ],
            }
        )


def test_validate_config_file(tmp_path: Path) -> None:
    path = tmp_path / "agentconnect.toml"
    path.write_text("team = true\n", encoding="utf-8")
    assert validate_config_file(path) is False
    save_example_config(path)
    assert validate_config_file(path) is True
