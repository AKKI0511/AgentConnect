"""Load a Team file and generate the example from the models.

Discovery walks from the start directory toward the filesystem root and
stops at the first Team file. In each directory, `agentconnect.toml`
beats `[tool.agentconnect]` in `pyproject.toml`. Files are never merged.
An explicit path skips discovery. A missing or invalid explicit path
fails.

Relative `module:Name` imports resolve from the chosen file's directory.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Iterator, Optional

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
    "# `class` is a BaseAgent subclass or create(name) -> BaseAgent.\n"
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
    table = _tool_table(data)
    if table is not None:
        return table
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

    An explicit path is not replaced with another file. `pyproject.toml`
    must contain `[tool.agentconnect]`.

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
    """Serialize `config` as a `[tool.agentconnect]` table."""
    data: dict[str, object] = config.model_dump(by_alias=True, exclude_none=True)
    lines = ["[tool.agentconnect]"]
    for key in ("team", "store", "embeddings", "host", "port", "require_join_auth"):
        lines.append(f"{key} = {_toml_literal(data[key])}")
    tools = data.get("tools") or []
    if tools:
        lines.append(f"tools = {_toml_literal(tools)}")
    for agent in config.agents:
        lines.append("")
        lines.append("[[tool.agentconnect.agents]]")
        lines.append(f"class = {_toml_literal(agent.class_path)}")
        lines.append(f"name = {_toml_literal(agent.name)}")
    return "\n".join(lines) + "\n"


def render_example_toml() -> str:
    """Return the commented example generated from `TeamConfig.example`."""
    return _EXAMPLE_HEADER + dump_team_toml(TeamConfig.example())
