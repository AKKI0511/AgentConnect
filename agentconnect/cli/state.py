"""Local state for a Team started by ``agentconnect up``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

STATE_DIR = ".agentconnect"
STATE_NAME = "state.json"


def state_dir(root: Path) -> Path:
    """Return ``<root>/.agentconnect``."""
    return root / STATE_DIR


def state_path(root: Path) -> Path:
    """Return the state JSON path under ``root``."""
    return state_dir(root) / STATE_NAME


def write_state(root: Path, *, pid: int, url: str, team: str, config_file: str) -> Path:
    """Record the running Team so other commands can find it."""
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": int(pid),
        "url": url,
        "team": team,
        "config_file": config_file,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_state(root: Path) -> Optional[dict[str, Any]]:
    """Return saved state, or None when the file is missing."""
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def clear_state(root: Path) -> None:
    """Remove the state file if it exists."""
    path = state_path(root)
    try:
        path.unlink()
    except FileNotFoundError:
        return
