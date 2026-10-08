"""Resolve which Runtime origin a CLI command should talk to."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agentconnect.cli.state import read_state
from agentconnect.config.loaders import load_selected_team

DEFAULT_ORIGIN = "http://127.0.0.1:9000"


def resolve_runtime_origin(
    *,
    url: Optional[str] = None,
    file: Optional[Path] = None,
    start: Optional[Path] = None,
) -> str:
    """Return the Runtime origin for a CLI command.

    Precedence is `--url`, then `--file`, then saved `up` state, then the
    nearest discovered Team file, then loopback port 9000. An explicit
    `--file` that is missing or invalid does not fall back to state or
    another Team.

    Args:
        url: Runtime origin from `--url`.
        file: Team file from `--file`.
        start: Directory used for saved state and discovery. Defaults to cwd.

    Returns:
        Origin such as `http://127.0.0.1:9000`.

    Raises:
        FileNotFoundError: `--file` was given and does not exist.
        ValueError: `--file` or the discovered Team file is invalid.
    """
    if url:
        return url.rstrip("/")
    base = (start or Path.cwd()).resolve()
    if file is not None:
        _, config = load_selected_team(file, start=base)
        return f"http://{config.host}:{config.port}"
    try:
        config_path, config = load_selected_team(start=base)
    except FileNotFoundError:
        return DEFAULT_ORIGIN
    state = read_state(config_path)
    saved = state.get("url") if state else None
    if isinstance(saved, str) and saved.strip():
        return saved.rstrip("/")
    return f"http://{config.host}:{config.port}"
