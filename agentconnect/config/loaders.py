"""
Configuration loaders for AgentConnect.

This module implements the three-tier configuration precedence system:
1. Runtime kwargs (highest priority)
2. agentconnect.yaml file
3. Hard-coded defaults (lowest priority)

The loader automatically discovers and loads agentconnect.yaml from the project root
or current working directory and merges it with optional runtime overrides.
It does not read environment variables for general configuration. Environment variables
are reserved for secrets and are consumed directly by the specific subsystems that
require them (e.g., provider SDKs, external clients).
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from agentconnect.config.models import AgentConnectSettings

logger = logging.getLogger(__name__)


def _find_config_file() -> Optional[Path]:
    """
    Find agentconnect.yaml configuration file.

    Searches in order:
    1. Current working directory
    2. Project root (where pyproject.toml exists)
    3. Parent directories up to 5 levels

    Returns:
        Path to config file if found, None otherwise
    """
    config_filename = "agentconnect.yaml"

    # Check current working directory first
    cwd_config = Path.cwd() / config_filename
    if cwd_config.exists():
        return cwd_config

    # Check for project root (where pyproject.toml exists)
    current_path = Path.cwd()
    for _ in range(5):  # Search up to 5 levels
        pyproject_path = current_path / "pyproject.toml"
        config_path = current_path / config_filename

        if pyproject_path.exists() and config_path.exists():
            return config_path

        # Move up one level
        parent_path = current_path.parent
        if parent_path == current_path:  # Reached root
            break
        current_path = parent_path

    # Check if we're in the AgentConnect package directory
    try:
        # Try to find the config relative to this module
        module_dir = Path(__file__).parent.parent.parent  # Go up to project root
        config_path = module_dir / config_filename
        if config_path.exists():
            return config_path
    except Exception:
        pass

    return None


def _load_yaml_config() -> Dict[str, Any]:
    """
    Load configuration from agentconnect.yaml file.

    Returns:
        Configuration dictionary from YAML file, empty dict if not found or error
    """
    if not YAML_AVAILABLE:
        logger.debug("PyYAML not available, skipping YAML config loading")
        return {}

    config_path = _find_config_file()
    if not config_path:
        logger.debug("No agentconnect.yaml found, using defaults")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        logger.info("Loaded configuration from %s", config_path)
        return config_data

    except yaml.YAMLError:
        logger.error("Error parsing YAML config file %s", config_path, exc_info=True)
        return {}
    except Exception:
        logger.error("Error reading config file %s", config_path, exc_info=True)
        return {}


def _merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge configuration dictionaries.

    Override values take precedence over base values.
    Nested dictionaries are merged recursively.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _merge_configs(result[key], value)
        else:
            # Override value
            result[key] = value

    return result


def load_settings(**overrides) -> AgentConnectSettings:
    """
    Load AgentConnect configuration with three-tier precedence.

    Precedence (highest to lowest):
    1. Runtime overrides (kwargs)
    2. agentconnect.yaml file
    3. Hard-coded defaults

    Args:
        **overrides: Runtime configuration overrides

    Returns:
        Fully configured AgentConnectSettings instance

    Example:
        .. code-block:: python

            # Load with defaults
            settings = load_settings()

            # Override specific settings at runtime
            settings = load_settings(
                registry={'vector_search': {'deployment': {'type': 'in_memory'}}},
            )
    """
    # Start with YAML configuration
    yaml_config = _load_yaml_config()

    # Apply runtime overrides
    if overrides:
        config_data = _merge_configs(yaml_config, overrides)
        logger.debug("Applied runtime configuration overrides")
    else:
        config_data = yaml_config

    # Create settings instance from merged config
    try:
        settings = AgentConnectSettings.create_from_dict(config_data)
        return settings
    except Exception:
        logger.error("Error creating settings from config", exc_info=True)
        # Fallback to defaults if config is invalid
        logger.warning("Falling back to default configuration")
        return AgentConnectSettings()


def create_example_config() -> str:
    """
    Create an example `agentconnect.yaml` configuration file content.

    Returns:
        YAML configuration string with examples and comments
    """
    return """# AgentConnect Configuration
# This file contains developer-facing configuration options.
# Secrets and API keys should be set as environment variables, not here.

# Global settings
project_name: "AgentConnect"

# Agent Registry configuration
registry:
  vector_search:
    model_name: "sentence-transformers/all-mpnet-base-v2"
    cache_folder: "./.cache/huggingface/embeddings"
    vector_store_path: "./.cache/vector_stores"
    deployment:
      type: "in_memory"

# Payments configuration
# Non-secrets only. CDP API keys must be provided via environment variables:
#   - CDP_API_KEY_NAME
#   - CDP_API_KEY_PRIVATE_KEY
payments:
  default_token_symbol: "USDC"      # e.g., USDC or ETH; drives ERC-20 vs native tools
  wallet_data_dir: "data/agent_wallets"  # where agent wallets are stored (non-secret path)

# Communication system settings - A2A messaging configuration
communication:
  enable_message_history: true  # Track message history (disable for performance)

# Client configurations
clients:
  registry:
    base_url: "http://localhost:8000"

# MCP (Model Context Protocol) configuration
mcp:
  agent_discovery:
    enabled: true
    top_k: 5
    strictness: 0.2
    output_detail: "summary"  # minimal | summary | capabilities | full
"""


def save_example_config(path: Optional[Path] = None) -> Path:
    """
    Save an example configuration file to disk.

    Args:
        path: Where to save the file. Defaults to agentconnect.yaml in current directory.

    Returns:
        Path where the file was saved
    """
    if path is None:
        path = Path.cwd() / "agentconnect.yaml"

    config_content = create_example_config()

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(config_content)
        logger.info("Example configuration saved to %s", path)
        return path
    except Exception:
        logger.error("Error saving example config to %s", path, exc_info=True)
        raise


def validate_config_file(path: Path) -> bool:
    """
    Validate a configuration file.

    Args:
        path: Path to the configuration file

    Returns:
        True if valid, False otherwise
    """
    try:
        if not YAML_AVAILABLE:
            logger.error("PyYAML not available for validation")
            return False

        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        # Try to create settings instance
        AgentConnectSettings.create_from_dict(config_data)
        logger.info("Configuration file %s is valid", path)
        return True

    except yaml.YAMLError:
        logger.error("YAML syntax error in %s", path, exc_info=True)
        return False
    except Exception:
        logger.error("Configuration validation error in %s", path, exc_info=True)
        return False
