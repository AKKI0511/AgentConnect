"""Discover and load a Team file.

Discovery walks from the start directory toward the filesystem root and
stops at the first Team file. In each directory, `agentconnect.toml`
beats `[tool.agentconnect]` in `pyproject.toml`. Files are never merged.
An explicit path skips discovery. A missing or invalid explicit path
fails.

A standalone `agentconnect.toml` uses the unprefixed tree. Only
`pyproject.toml` wraps it in `[tool.agentconnect]`.

Relative `module:Name` imports resolve from the chosen file's directory.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Iterator, Optional

import tomli_w

from agentconnect.config.models import TeamConfig

TOML_FILENAME = "agentconnect.toml"
PYPROJECT_FILENAME = "pyproject.toml"
_YAML_SUFFIXES = {".yaml", ".yml"}

_EXAMPLE_HEADER = (
    "# Describes a Team and the Agents this process hosts.\n"
    '# Embedded Team("name").start() needs no file.\n'
    "# Secrets stay in the environment.\n"
    "#\n"
    "# store: memory  or  redis://localhost:6379/0\n"
    "# embeddings: auto | none | hashed | fastembed | openai | litellm:<model>\n"
    "# auto never sends Profiles or queries to a hosted embedder.\n"
    "#\n"
    "# Agents listed here are constructed by `agentconnect up`.\n"
    "# `entrypoint` is a BaseAgent subclass or create(name, **kwargs) -> BaseAgent.\n"
    "# Optional `kwargs` belong to that class or factory. Do not put `name` there.\n"
    "# Agents in other processes join by URL with a token from\n"
    "# `agentconnect token issue` and are not listed here.\n"
    "#\n"
    "# Extra `tools` are published on Team MCP. Connecting a harness is\n"
    "# a separate step: add the Team MCP URL there.\n"
    "#\n"
    "# Nearest directory wins. In that directory, agentconnect.toml beats\n"
    "# [tool.agentconnect] in pyproject.toml. Files are never merged.\n"
    "\n"
)


def _ancestors(start: Optional[Path]) -> Iterator[Path]:
    probe = (start or Path.cwd()).resolve()
    while True:
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


def _load_toml(path: Path) -> dict[str, object]:
    try:
        data = tomllib.loads(_read_text(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a TOML table")
    return data


def _tool_table(data: dict[str, object]) -> dict[str, object] | None:
    tool = data.get("tool")
    if not isinstance(tool, dict) or "agentconnect" not in tool:
        return None
    table = tool.get("agentconnect")
    if not isinstance(table, dict):
        raise ValueError("[tool.agentconnect] must be a table")
    return table


def _pyproject_team_table(path: Path) -> dict[str, object] | None:
    data = _load_toml(path)
    try:
        return _tool_table(data)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def _mapping_from_toml_file(path: Path) -> dict[str, object]:
    data = _load_toml(path)
    if path.name == PYPROJECT_FILENAME:
        table = _tool_table(data)
        if table is None:
            raise ValueError(f"{path} has no [tool.agentconnect] table")
        return table
    try:
        wrapped = _tool_table(data)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    if wrapped is not None:
        raise ValueError(
            f"{path} must not wrap Team settings in [tool.agentconnect]; "
            "use that table only in pyproject.toml"
        )
    return data


def _mapping_from_file(path: Path) -> dict[str, object]:
    if path.suffix.lower() in _YAML_SUFFIXES:
        raise ValueError(
            f"{path} is a YAML file. Team files are TOML: agentconnect.toml, "
            "or pyproject.toml with [tool.agentconnect]."
        )
    if path.suffix.lower() != ".toml":
        raise ValueError(
            f"{path} is not a Team file. Use agentconnect.toml, or "
            "pyproject.toml with [tool.agentconnect]."
        )
    return _mapping_from_toml_file(path)


def find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Return the nearest Team file from `start`, or None.

    At each directory, `agentconnect.toml` beats `[tool.agentconnect]`
    in `pyproject.toml`.

    Raises:
        ValueError: A candidate `pyproject.toml` exists but cannot be parsed.
    """
    for directory in _ancestors(start):
        toml_path = directory / TOML_FILENAME
        if toml_path.is_file():
            return toml_path
        pyproject = directory / PYPROJECT_FILENAME
        if pyproject.is_file() and _pyproject_team_table(pyproject) is not None:
            return pyproject
    return None


def load_team_config(
    path: Optional[Path] = None, *, start: Optional[Path] = None
) -> TeamConfig:
    """Load and validate a Team file.

    An explicit path is not replaced with another file. A standalone
    `agentconnect.toml` must not wrap settings in `[tool.agentconnect]`.
    `pyproject.toml` must contain that table.

    Raises:
        FileNotFoundError: No Team file exists.
        ValueError: The file is malformed or fails validation.
    """
    config_path: Path | None
    if path is not None:
        config_path = path
        if not config_path.is_file():
            raise FileNotFoundError(f"Team file was not found: {config_path}")
    else:
        found_path = find_config_file(start)
        config_path = found_path
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

    An explicit path must exist and be valid. This never chooses a
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


def _team_toml_data(config: TeamConfig) -> dict[str, object]:
    data: dict[str, object] = {
        "team": config.team,
        "store": config.store,
        "embeddings": config.embeddings,
        "host": config.host,
        "port": config.port,
        "require_join_auth": config.require_join_auth,
    }
    if config.tools:
        data["tools"] = list(config.tools)
    if config.agents:
        agents: dict[str, object] = {}
        for name, spec in config.agents.items():
            entry: dict[str, object] = {"entrypoint": spec.entrypoint}
            if spec.kwargs:
                entry["kwargs"] = spec.kwargs
            agents[name] = entry
        data["agents"] = agents
    return data


def _reject_toml_nulls(value: object, path: str) -> None:
    if value is None:
        label = path if path else "value"
        raise ValueError(f"{label} is null; TOML cannot represent it")
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            _reject_toml_nulls(item, child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_toml_nulls(item, f"{path}[{index}]")


def dump_team_toml(config: TeamConfig, *, pyproject: bool = False) -> str:
    """Serialize a Team file.

    The default is the unprefixed tree for `agentconnect.toml`.
    `pyproject=True` wraps the same tree under `[tool.agentconnect]`.

    Raises:
        ValueError: A JSON null appears in the tree. The message names
            that option. TOML has no null.
    """
    data = _team_toml_data(config)
    payload: dict[str, object] = {"tool": {"agentconnect": data}} if pyproject else data
    _reject_toml_nulls(payload, "")
    dumped = tomli_w.dumps(payload)
    return dumped if dumped.endswith("\n") else dumped + "\n"


def render_example_toml() -> str:
    """Commented example for a standalone `agentconnect.toml`."""
    return _EXAMPLE_HEADER + dump_team_toml(TeamConfig.example())
