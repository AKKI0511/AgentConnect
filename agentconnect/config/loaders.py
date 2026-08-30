"""Load ``agentconnect.yaml`` and generate the example file from the models.

Discovery order:

1. ``--file`` path passed by the caller
2. current working directory
3. nearest parent that contains ``pyproject.toml``, up to five levels

    from agentconnect.config import load_team_config

    config = load_team_config()
    config.team
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from agentconnect.config.models import TeamConfig

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "agentconnect.yaml"


def find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Return the first ``agentconnect.yaml`` above ``start``, or None."""
    current = (start or Path.cwd()).resolve()
    cwd_config = current / CONFIG_FILENAME
    if cwd_config.is_file():
        return cwd_config
    probe = current
    for _ in range(5):
        pyproject = probe / "pyproject.toml"
        config_path = probe / CONFIG_FILENAME
        if pyproject.is_file() and config_path.is_file():
            return config_path
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    return None


def load_team_config(
    path: Optional[Path] = None, *, start: Optional[Path] = None
) -> TeamConfig:
    """Load and validate a Team file.

    Raises ``FileNotFoundError`` when no file exists, ``ValueError`` when
    YAML is missing or the document is invalid.
    """
    if not YAML_AVAILABLE:
        raise ValueError("PyYAML is required to load agentconnect.yaml")
    config_path = path if path is not None else find_config_file(start)
    if config_path is None:
        raise FileNotFoundError("agentconnect.yaml was not found")
    try:
        text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not read {config_path}: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("agentconnect.yaml must be a mapping")
    try:
        return TeamConfig.model_validate(data)
    except Exception as exc:
        raise ValueError(f"invalid Team file {config_path}: {exc}") from exc


def render_example_yaml() -> str:
    """Return example YAML generated from :meth:`TeamConfig.example`."""
    example = TeamConfig.example()
    data: dict[str, Any] = example.model_dump(by_alias=True, exclude_none=True)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    header = (
        "# Describes a Team and the Agents this process hosts.\n"
        '# Embedded Team("name").start() needs no file.\n'
        "# Secrets stay in the environment.\n"
        "#\n"
        "# store: memory  or  redis://localhost:6379/0\n"
        "# embeddings: auto | none | fastembed | litellm:<model>\n"
        "#\n"
        "# Agents listed here are constructed by `agentconnect up`.\n"
        "# Agents in other processes join by URL with a token from\n"
        "# `agentconnect token issue`.\n"
        "\n"
    )
    return header + body


def save_example_config(path: Optional[Path] = None) -> Path:
    """Write the generated example YAML to ``path``."""
    target = path if path is not None else Path.cwd() / CONFIG_FILENAME
    target.write_text(render_example_yaml(), encoding="utf-8")
    logger.info("Wrote Team file %s", target)
    return target


def validate_config_file(path: Path) -> bool:
    """Return True when ``path`` is a valid Team file."""
    try:
        load_team_config(path)
        return True
    except (ValueError, FileNotFoundError, OSError):
        logger.error("Configuration validation failed for %s", path, exc_info=True)
        return False
