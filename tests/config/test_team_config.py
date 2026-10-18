"""Team file models and TOML discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentconnect.config.loaders import (
    dump_team_toml,
    find_config_file,
    load_team_config,
    render_example_toml,
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
    assert parsed.model_dump() == TeamConfig.example().model_dump()


def test_load_team_config_from_cwd_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "agentconnect.toml").write_text(render_example_toml(), encoding="utf-8")
    config = load_team_config()
    assert config.team == "content-squad"
    assert config.agents["researcher"].entrypoint.startswith("agents.")
    assert find_config_file() == tmp_path / "agentconnect.toml"


def test_load_pyproject_tool_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "pyproject.toml",
        dump_team_toml(TeamConfig(team="from-pyproject"), pyproject=True),
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
        dump_team_toml(TeamConfig(team="from-pyproject"), pyproject=True),
    )
    assert load_team_config().team == "from-toml"
    assert find_config_file() == tmp_path / "agentconnect.toml"


def test_yaml_in_cwd_does_not_hide_parent_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    nested = project / "nested"
    nested.mkdir(parents=True)
    _write(
        project / "pyproject.toml",
        dump_team_toml(TeamConfig(team="from-parent"), pyproject=True),
    )
    _write(nested / "agentconnect.yaml", "team: from-yaml\n")
    monkeypatch.chdir(nested)
    assert load_team_config().team == "from-parent"
    assert find_config_file() == project / "pyproject.toml"


def test_yaml_is_not_a_team_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = _write(tmp_path / "agentconnect.yml", "team: legacy-yaml\n")
    with pytest.raises(FileNotFoundError, match="Team file was not found"):
        load_team_config()
    assert find_config_file() is None
    with pytest.raises(ValueError, match="YAML"):
        load_team_config(path)


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


def test_explicit_missing_file_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "agentconnect.toml", dump_team_toml(TeamConfig(team="cwd-team")))
    missing = tmp_path / "missing.toml"
    with pytest.raises(FileNotFoundError, match="Team file was not found"):
        load_team_config(missing)


def test_agentconnect_toml_accepts_bare_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "agentconnect.toml",
        'team = "bare-keys"\nstore = "memory"\n',
    )
    assert load_team_config().team == "bare-keys"


def test_standalone_toml_rejects_tool_wrap(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "agentconnect.toml",
        dump_team_toml(TeamConfig(team="wrapped"), pyproject=True),
    )
    with pytest.raises(ValueError, match="tool.agentconnect"):
        load_team_config(path)


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
    with pytest.raises(ValidationError):
        TeamConfig.model_validate({"team": "content-squad", "publish": ["writer"]})
    with pytest.raises(ValidationError):
        HostedAgentConfig.model_validate(
            {"entrypoint": "agents.writer:Writer", "class": "agents.writer:Writer"}
        )


def test_store_and_embeddings_validation() -> None:
    TeamConfig.model_validate({"team": "demo", "store": "redis://localhost:6379/0"})
    TeamConfig.model_validate(
        {"team": "demo", "embeddings": "litellm:text-embedding-3-small"}
    )
    TeamConfig.model_validate({"team": "demo", "embeddings": "openai"})
    with pytest.raises(ValidationError):
        TeamConfig.model_validate({"team": "demo", "store": "postgres://x"})
    with pytest.raises(ValidationError):
        TeamConfig.model_validate({"team": "demo", "embeddings": "torch"})
    with pytest.raises(ValidationError):
        TeamConfig.model_validate({"team": "demo", "host": "0.0.0.0"})


def test_hosted_agent_entrypoint() -> None:
    config = TeamConfig.model_validate(
        {
            "team": "demo",
            "agents": {"Writer": {"entrypoint": "agents.writer:Writer"}},
        }
    )
    assert list(config.agents) == ["writer"]
    assert config.agents["writer"].entrypoint == "agents.writer:Writer"
    with pytest.raises(ValidationError):
        HostedAgentConfig.model_validate({"entrypoint": "agents.writer"})


def test_named_agents_mapping_loads(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "agentconnect.toml",
        (
            'team = "content-squad"\n'
            "\n"
            "[agents.researcher]\n"
            'entrypoint = "agents.researcher:Researcher"\n'
            "\n"
            "[agents.writer]\n"
            'entrypoint = "agents.writer:Writer"\n'
            'kwargs.model = "provider/model"\n'
        ),
    )
    config = load_team_config(path)
    assert list(config.agents) == ["researcher", "writer"]
    assert config.agents["researcher"].kwargs == {}
    assert config.agents["writer"].kwargs == {"model": "provider/model"}


def test_writer_writer_name_collision_is_rejected() -> None:
    with pytest.raises(ValidationError, match="collide"):
        TeamConfig.model_validate(
            {
                "team": "demo",
                "agents": {
                    "Writer": {"entrypoint": "agents.writer:Writer"},
                    "writer": {"entrypoint": "agents.other:Other"},
                },
            }
        )


def test_invalid_agent_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="valid Agent name"):
        TeamConfig.model_validate(
            {
                "team": "demo",
                "agents": {"bad name": {"entrypoint": "agents.writer:Writer"}},
            }
        )


def test_agents_array_is_rejected() -> None:
    with pytest.raises(ValidationError, match="table of Agent names"):
        TeamConfig.model_validate(
            {
                "team": "demo",
                "agents": [
                    {"entrypoint": "agents.writer:Writer", "name": "writer"},
                ],
            }
        )


def test_competing_kwargs_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="kwargs must not include name"):
        HostedAgentConfig.model_validate(
            {
                "entrypoint": "agents.writer:Writer",
                "kwargs": {"name": "other"},
            }
        )


def test_dump_rejects_json_null() -> None:
    config = TeamConfig(
        team="demo",
        agents={
            "writer": HostedAgentConfig(
                entrypoint="agents.writer:Writer",
                kwargs={"model": None},
            )
        },
    )
    with pytest.raises(ValueError, match=r"agents\.writer\.kwargs\.model is null"):
        dump_team_toml(config)


def test_nested_kwargs_roundtrip_through_toml_writer(tmp_path: Path) -> None:
    config = TeamConfig(
        team="demo",
        agents={
            "writer": HostedAgentConfig(
                entrypoint="agents.writer:Writer",
                kwargs={
                    "model": "provider/model",
                    "note": 'line1\nline2\tquoted"slash\\end',
                    "limits": {"max_tokens": 100, "stop": ["END", "STOP"]},
                },
            )
        },
    )
    path = tmp_path / "agentconnect.toml"
    path.write_text(dump_team_toml(config), encoding="utf-8")
    loaded = load_team_config(path)
    assert loaded.agents["writer"].kwargs == config.agents["writer"].kwargs
    text = path.read_text(encoding="utf-8")
    assert "[tool.agentconnect]" not in text
    assert "entrypoint" in text


def test_pyproject_wrap_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = TeamConfig(
        team="from-pyproject",
        agents={
            "writer": HostedAgentConfig(
                entrypoint="agents.writer:Writer",
                kwargs={"model": "provider/model"},
            )
        },
    )
    text = dump_team_toml(config, pyproject=True)
    assert "[tool.agentconnect]" in text
    (tmp_path / "pyproject.toml").write_text(text, encoding="utf-8")
    loaded = load_team_config()
    assert loaded.team == "from-pyproject"
    assert loaded.agents["writer"].kwargs["model"] == "provider/model"


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
    _write(
        nested / "pyproject.toml",
        dump_team_toml(TeamConfig(team="nearest"), pyproject=True),
    )
    monkeypatch.chdir(nested)
    assert load_team_config().team == "nearest"
    assert find_config_file() == nested / "pyproject.toml"
