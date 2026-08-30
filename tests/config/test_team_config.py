"""Team file models and example YAML generated from those models."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentconnect.config.loaders import (
    find_config_file,
    load_team_config,
    render_example_yaml,
    save_example_config,
    validate_config_file,
)
from agentconnect.config.models import HostedAgentConfig, PaymentsSettings, TeamConfig


def test_example_yaml_matches_models() -> None:
    committed = Path("agentconnect/config/agentconnect.example.yaml").read_text(
        encoding="utf-8"
    )
    assert committed.replace("\r\n", "\n") == render_example_yaml().replace(
        "\r\n", "\n"
    )
    loaded = yaml.safe_load(committed)
    parsed = TeamConfig.model_validate(loaded)
    assert parsed.model_dump(by_alias=True) == TeamConfig.example().model_dump(
        by_alias=True
    )


def test_load_team_config_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    save_example_config(tmp_path / "agentconnect.yaml")
    config = load_team_config()
    assert config.team == "content-squad"
    assert config.agents[0].class_path.startswith("agents.")
    assert find_config_file() == tmp_path / "agentconnect.yaml"


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(Exception):
        TeamConfig.model_validate({"team": "content-squad", "publish": ["writer"]})


def test_store_and_embeddings_validation() -> None:
    TeamConfig.model_validate({"team": "demo", "store": "redis://localhost:6379/0"})
    TeamConfig.model_validate(
        {"team": "demo", "embeddings": "litellm:text-embedding-3-small"}
    )
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


def test_validate_config_file(tmp_path: Path) -> None:
    path = tmp_path / "agentconnect.yaml"
    path.write_text("team: not a name\n", encoding="utf-8")
    assert validate_config_file(path) is False
    save_example_config(path)
    assert validate_config_file(path) is True


def test_payments_symbol_normalization() -> None:
    assert PaymentsSettings(default_token_symbol="usdc").default_token_symbol == "USDC"
