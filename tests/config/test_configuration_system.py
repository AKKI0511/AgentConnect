"""Behavioral tests for the AgentConnect configuration system.

Focus on invariants and precedence rather than brittle hard-coded defaults.
"""

import json
from pathlib import Path

import pytest

from agentconnect.config.models import (
    AgentConnectSettings,
    LoggingSettings,
    PaymentsSettings,
)
from pydantic import SecretStr
from agentconnect.config.loaders import load_settings, _merge_configs
from agentconnect.servers.config import RegistryAPISettings


# ---------------------------------------------------------------------------
# Validation and invariants (no brittle defaults)
# ---------------------------------------------------------------------------


def test_logging_settings_allowed_levels():
    """LoggingSettings remains available; values normalize to allowed set."""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "invalid"]:
        cfg = LoggingSettings(level=level)
        assert cfg.level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def test_registry_api_settings_invariants():
    """Server settings should have sane types and validated ranges without asserting exact defaults."""
    s = RegistryAPISettings()
    assert isinstance(s.host, str) and s.host
    assert isinstance(s.port, int) and 1 <= s.port <= 65535
    assert s.log_level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    assert isinstance(s.allowed_origins, list) and all(isinstance(x, str) for x in s.allowed_origins)
    # vector_search should be a structured object
    assert hasattr(s, "vector_search")


# ---------------------------------------------------------------------------
# Precedence: runtime > YAML > defaults; YAML discovery
# ---------------------------------------------------------------------------


def test_precedence_runtime_over_yaml_and_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Create temp YAML
    yaml_content = (
        "clients:\n"
        "  registry:\n"
        "    base_url: 'http://from-yaml:8000'\n"
    )
    (tmp_path / "agentconnect.yaml").write_text(yaml_content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # YAML should be picked up
    s_yaml = load_settings()
    assert s_yaml.clients.registry.base_url == "http://from-yaml:8000"

    # Runtime override should win over YAML
    s_rt = load_settings(clients={"registry": {"base_url": "http://runtime-override"}})
    assert s_rt.clients.registry.base_url == "http://runtime-override"


def test_yaml_discovery_in_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "agentconnect.yaml").write_text("project_name: 'FromYAML'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    s = load_settings()
    assert s.project_name == "FromYAML"


# ---------------------------------------------------------------------------
# Env isolation for general config; secrets pass-through for subsystems
# ---------------------------------------------------------------------------


def test_env_isolation_general_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # Pretend someone set an env override – global settings must ignore it
    monkeypatch.setenv("AGENTCONNECT_CLIENTS__REGISTRY__BASE_URL", "http://env-override")

    # YAML defines the value; loader must honor YAML, not env
    (tmp_path / "agentconnect.yaml").write_text(
        "clients:\n  registry:\n    base_url: 'http://yaml-value'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    s = load_settings()
    assert s.clients.registry.base_url == "http://yaml-value"


def test_secrets_pass_through_for_remote_qdrant(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QDRANT_API_KEY", "TOPSECRET")
    s = AgentConnectSettings.create_from_dict(
        {
            "registry": {
                "vector_search": {
                    "deployment": {"type": "remote", "url": "https://example.com"}
                }
            }
        }
    )
    assert s.registry.vector_search.deployment.api_key.get_secret_value() == "TOPSECRET"


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------


def test_merge_configs_deep_and_lists():
    base = {"a": [1, 2], "nested": {"x": 1, "list": [10, 20]}}
    override = {"a": [9], "nested": {"y": 2, "list": [99]}}
    merged = _merge_configs(base, override)
    assert merged["a"] == [9]
    assert merged["nested"]["x"] == 1 and merged["nested"]["y"] == 2
    # Lists are replaced, not merged
    assert merged["nested"]["list"] == [99]


# ---------------------------------------------------------------------------
# Validation behaviors
# ---------------------------------------------------------------------------


def test_vector_search_remote_url_validation():
    # Malformed URL should trigger validation error
    with pytest.raises(ValueError):
        AgentConnectSettings.create_from_dict(
            {
                "registry": {
                    "vector_search": {
                        "deployment": {"type": "remote", "url": "localhost:6333"}
                    }
                }
            }
        )


def test_payments_symbol_normalization():
    p = PaymentsSettings(default_token_symbol="usdc")
    assert p.default_token_symbol == "USDC"


# ---------------------------------------------------------------------------
# Servers config – env parsing and precedence for JSON override
# ---------------------------------------------------------------------------


def test_registry_api_settings_allowed_origins_parsing(monkeypatch: pytest.MonkeyPatch):
    # JSON string
    monkeypatch.setenv("AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS", "[\"https://a.com\", \"https://b.com\"]")
    s_json = RegistryAPISettings()
    assert s_json.allowed_origins == ["https://a.com", "https://b.com"]

    # CSV string
    monkeypatch.setenv("AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS", "https://a.com,https://b.com")
    s_csv = RegistryAPISettings()
    assert s_csv.allowed_origins == ["https://a.com", "https://b.com"]


def test_registry_api_settings_vector_search_json_precedence(monkeypatch: pytest.MonkeyPatch):
    # Nested keys suggest in_memory, but JSON override sets remote
    monkeypatch.setenv("AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE", "in_memory")
    monkeypatch.setenv(
        "AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON",
        json.dumps({"deployment": {"type": "remote", "url": "https://remote.example"}}),
    )
    s = RegistryAPISettings()
    assert s.vector_search.deployment.type == "remote"
    assert getattr(s.vector_search.deployment, "url", None) == "https://remote.example"


# ---------------------------------------------------------------------------
# MCP config – runtime overrides
# ---------------------------------------------------------------------------


def test_mcp_runtime_overrides_apply():
    s = AgentConnectSettings.create_from_dict(
        {
            "mcp": {
                "agent_discovery": {
                    "enabled": False,
                    "top_k": 7,
                    "strictness": 0.4,
                    "output_detail": "capabilities",
                }
            }
        }
    )
    assert s.mcp.agent_discovery.enabled is False
    assert isinstance(s.mcp.agent_discovery.top_k, int) and s.mcp.agent_discovery.top_k == 7
    assert isinstance(s.mcp.agent_discovery.strictness, float) and s.mcp.agent_discovery.strictness == 0.4
    assert s.mcp.agent_discovery.output_detail == "capabilities"


def test_loader_returns_settings_instance():
    assert isinstance(load_settings(), AgentConnectSettings)


def test_yaml_safe_dump_redacts_secrets():
    # Build a config dict that includes a remote deployment with an api_key
    secret_value = "SUPERSECRETKEY"
    cfg = AgentConnectSettings.create_from_dict(
        {
            "registry": {
                "vector_search": {
                    "deployment": {
                        "type": "remote",
                        "url": "https://example.com",
                    }
                }
            }
        }
    )
    # Manually set the secret (simulating env or runtime)
    if hasattr(cfg.registry.vector_search.deployment, "api_key"):
        cfg.registry.vector_search.deployment.api_key = SecretStr(secret_value)

    safe = cfg.model_dump_yaml_safe()

    # Ensure the nested key path exists
    dep = safe["registry"]["vector_search"]["deployment"]
    assert "api_key" in dep
    assert dep["api_key"] == "***REDACTED***"


if __name__ == "__main__":
    pytest.main([__file__])
