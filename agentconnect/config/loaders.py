"""Load a Team file and generate the example from the models.

Discovery is nearest-directory first and never merged. At each directory,
from the start path toward the filesystem root:

1. `agentconnect.toml`
2. `[tool.agentconnect]` in `pyproject.toml`

`agentconnect.yaml` / `agentconnect.yml` is last-resort compatibility,
considered only after no TOML Team file exists in this directory or any
ancestor. An explicit path skips discovery and never falls back to
another file. Relative `module:Name` imports resolve from the chosen
file's directory.

    from agentconnect.config import load_team_config

    config = load_team_config()
    config.team
"""

from __future__ import annotations

import logging
import tomllib
import warnings
from pathlib import Path
from typing import Any, Iterator, Optional

from agentconnect.config.models import TeamConfig

logger = logging.getLogger(__name__)

TOML_FILENAME = "agentconnect.toml"
PYPROJECT_FILENAME = "pyproject.toml"
YAML_FILENAMES = ("agentconnect.yaml", "agentconnect.yml")
_MAX_PARENTS = 16
_YAML_SUFFIXES = {".yaml", ".yml"}

_EXAMPLE_HEADER = (
    "# Describes a Team and the Agents this process hosts.\n"
    '# Embedded Team("name").start() needs no file.\n'
    "# Secrets stay in the environment.\n"
    "#\n"
    "# store: memory  or  redis://localhost:6379/0\n"
    "# embeddings: auto | none | fastembed | openai | litellm:<model>\n"
    "# auto never sends Profiles or queries to a hosted embedder.\n"
    "#\n"
    "# Agents listed here are constructed by `agentconnect up`.\n"
    "# `class` is a BaseAgent subclass or create(name) -> BaseAgent.\n"
    "# Agents in other processes join by URL with a token from\n"
    "# `agentconnect token issue` and are not listed here.\n"
    "#\n"
    "# Extra `tools` are published on Team MCP. Connecting a harness is\n"
    "# a separate step: add the Team MCP URL there.\n"
    "#\n"
    "# Nearest directory wins. In that directory, agentconnect.toml beats\n"
    "# [tool.agentconnect] in pyproject.toml. YAML is last-resort\n"
    "# compatibility after no ancestor TOML Team file exists. Files are\n"
    "# never merged.\n"
    "\n"
)


def _ancestors(start: Optional[Path]) -> Iterator[Path]:
    probe = (start or Path.cwd()).resolve()
    for _ in range(_MAX_PARENTS):
        yield probe
        parent = probe.parent
        if parent == probe:
            return
        probe = parent


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(_read_text(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a TOML table")
    return data


def _tool_table(data: dict[str, Any]) -> dict[str, Any] | None:
    tool = data.get("tool")
    if not isinstance(tool, dict) or "agentconnect" not in tool:
        return None
    table = tool.get("agentconnect")
    if not isinstance(table, dict):
        raise ValueError("[tool.agentconnect] must be a table")
    return table


def _pyproject_team_table(path: Path) -> dict[str, Any] | None:
    data = _load_toml(path)
    try:
        return _tool_table(data)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def _mapping_from_toml_file(path: Path) -> dict[str, Any]:
    data = _load_toml(path)
    if path.name == PYPROJECT_FILENAME:
        table = _tool_table(data)
        if table is None:
            raise ValueError(f"{path} has no [tool.agentconnect] table")
        return table
    table = _tool_table(data)
    if table is not None:
        return table
    return data


def _is_yaml_path(path: Path) -> bool:
    return path.suffix.lower() in _YAML_SUFFIXES


def _mapping_from_file(path: Path) -> dict[str, Any]:
    if _is_yaml_path(path):
        from agentconnect.compat.yaml import load_yaml_mapping

        warning = (
            f"Loading legacy YAML Team file {path}. Move this configuration to "
            "agentconnect.toml or [tool.agentconnect] in pyproject.toml."
        )
        warnings.warn(warning, DeprecationWarning, stacklevel=3)
        logger.warning(warning)
        return load_yaml_mapping(path)
    if path.suffix.lower() != ".toml":
        raise ValueError(
            f"{path} is not a Team file. Use agentconnect.toml, "
            "pyproject.toml with [tool.agentconnect], or a legacy .yaml file."
        )
    return _mapping_from_toml_file(path)


def find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Return the nearest Team file from ``start``, or None.

    At each directory, a dedicated TOML file beats ``[tool.agentconnect]``
    in ``pyproject.toml``. YAML is considered only after the walk finds
    no TOML Team file.

    Args:
        start: Directory to walk from. Defaults to the current directory.

    Raises:
        ValueError: A candidate file exists but cannot be parsed.
    """
    yaml_fallback: Path | None = None
    for directory in _ancestors(start):
        toml_path = directory / TOML_FILENAME
        if toml_path.is_file():
            return toml_path
        pyproject = directory / PYPROJECT_FILENAME
        if pyproject.is_file() and _pyproject_team_table(pyproject) is not None:
            return pyproject
        if yaml_fallback is None:
            for name in YAML_FILENAMES:
                candidate = directory / name
                if candidate.is_file():
                    yaml_fallback = candidate
                    break
    return yaml_fallback


def load_team_config(
    path: Optional[Path] = None, *, start: Optional[Path] = None
) -> TeamConfig:
    """Load and validate a Team file.

    Args:
        path: Explicit file. ``.toml`` is parsed with ``tomllib``.
            ``pyproject.toml`` requires ``[tool.agentconnect]``. ``.yaml``
            files go through the compatibility shim.
        start: Directory used when ``path`` is omitted.

    Returns:
        The validated Team configuration.

    Raises:
        FileNotFoundError: No Team file exists.
        ValueError: The file is malformed or fails validation.
    """
    if path is not None:
        config_path = path
        if not config_path.is_file():
            raise FileNotFoundError(f"Team file was not found: {config_path}")
    else:
        config_path = find_config_file(start)
        if config_path is None:
            raise FileNotFoundError(
                "Team file was not found. Create agentconnect.toml, add "
                "[tool.agentconnect] to pyproject.toml, or run 'agentconnect init'."
            )
    data = _mapping_from_file(config_path)
    try:
        return TeamConfig.model_validate(data)
    except Exception as exc:
        raise ValueError(f"invalid Team file {config_path}: {exc}") from exc


def load_selected_team(
    path: Optional[Path] = None,
    *,
    start: Optional[Path] = None,
) -> tuple[Path, TeamConfig]:
    """Load an explicit Team file, or the nearest discovered one.

    An explicit `path` must exist and be valid. This never chooses a
    different Team file.

    Returns:
        The resolved file path and its configuration.

    Raises:
        FileNotFoundError: No Team file was given or discovered.
        ValueError: The file exists but is not valid Team configuration.
    """
    if path is not None:
        resolved = path.expanduser()
        if not resolved.is_absolute():
            resolved = (start or Path.cwd()) / resolved
        resolved = resolved.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Team file was not found: {resolved}")
        return resolved, load_team_config(resolved)
    found = find_config_file(start)
    if found is None:
        raise FileNotFoundError(
            "Team file was not found. Create agentconnect.toml, add "
            "[tool.agentconnect] to pyproject.toml, or run 'agentconnect init'."
        )
    return found, load_team_config(found)


def _toml_literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        inner = ", ".join(_toml_literal(item) for item in value)
        return f"[{inner}]"
    raise TypeError(f"cannot encode {type(value).__name__} as TOML")


def dump_team_toml(config: TeamConfig) -> str:
    """Serialize ``config`` as a ``[tool.agentconnect]`` table."""
    data: dict[str, Any] = config.model_dump(by_alias=True, exclude_none=True)
    lines = ["[tool.agentconnect]"]
    for key in ("team", "store", "embeddings", "host", "port", "require_join_auth"):
        lines.append(f"{key} = {_toml_literal(data[key])}")
    tools = data.get("tools") or []
    if tools:
        lines.append(f"tools = {_toml_literal(tools)}")
    for agent in data.get("agents") or []:
        lines.append("")
        lines.append("[[tool.agentconnect.agents]]")
        lines.append(f"class = {_toml_literal(agent['class'])}")
        lines.append(f"name = {_toml_literal(agent['name'])}")
    return "\n".join(lines) + "\n"


def render_example_toml() -> str:
    """Return example TOML generated from `TeamConfig.example`."""
    return _EXAMPLE_HEADER + dump_team_toml(TeamConfig.example())


def save_example_config(path: Optional[Path] = None) -> Path:
    """Write the generated example TOML to ``path``."""
    target = path if path is not None else Path.cwd() / TOML_FILENAME
    target.write_text(render_example_toml(), encoding="utf-8")
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
