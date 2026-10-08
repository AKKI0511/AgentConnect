"""Per-configuration state for a Team started by ``agentconnect up``.

Publication and cleanup are ownership-aware. A process may overwrite or
delete the record only when it still names that launch.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from agentconnect.cli.process import inspect_process, process_created_token

STATE_DIR = ".agentconnect"
_LOCK_WAIT_SECONDS = 10.0


def state_dir(config_path: Path) -> Path:
    """Return ``<config-dir>/.agentconnect``."""
    return config_path.resolve().parent / STATE_DIR


def state_path(config_path: Path) -> Path:
    """Return the state JSON path for this Team file."""
    resolved = config_path.resolve()
    return state_dir(resolved) / f"{resolved.name}.json"


def write_state(
    config_path: Path,
    *,
    pid: int,
    url: str,
    team: str,
    created: Optional[str] = None,
) -> Path:
    """Record the running Team for this configuration."""
    resolved = config_path.resolve()
    path = state_path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = created if created is not None else process_created_token(pid)
    payload: dict[str, Any] = {
        "pid": int(pid),
        "url": url,
        "team": team,
        "config_file": str(resolved),
    }
    if token:
        payload["created"] = token
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def publish_state(
    config_path: Path,
    *,
    pid: int,
    url: str,
    team: str,
    created: str,
) -> Path:
    """Write launch state if the previous record is gone or was reused.

    An existing record whose owner cannot be verified is left in place.
    """
    if not created:
        raise RuntimeError("could not read process identity")
    with _state_lock(config_path):
        existing = read_state(config_path)
        if existing:
            _require_replaceable(existing, pid=pid, created=created)
        return write_state(config_path, pid=pid, url=url, team=team, created=created)


def _require_replaceable(
    existing: dict[str, Any],
    *,
    pid: int,
    created: str,
) -> None:
    existing_pid = existing.get("pid")
    recorded = existing.get("created")
    if existing_pid == pid and recorded == created:
        return
    if not isinstance(existing_pid, int):
        raise RuntimeError("cannot verify existing Team process identity")
    status, live = inspect_process(existing_pid)
    if status == "dead":
        return
    if (
        status == "live"
        and isinstance(recorded, str)
        and recorded
        and live is not None
        and live != recorded
    ):
        return
    if status == "live" and isinstance(recorded, str) and recorded and live == recorded:
        raise RuntimeError(
            f"Team {existing.get('team')} already running at "
            f"{existing.get('url')} (pid {existing_pid})"
        )
    raise RuntimeError("cannot verify existing Team process identity")


def read_state(config_path: Path) -> Optional[dict[str, Any]]:
    """Return saved state for this Team file, or None when missing."""
    path = state_path(config_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def clear_state(config_path: Path) -> None:
    """Remove the state file for this Team file if it exists."""
    path = state_path(config_path)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def clear_owned_state(
    config_path: Path,
    *,
    pid: int,
    created: Optional[str],
) -> bool:
    """Delete the record only when it still names this launch.

    Returns:
        True when this call removed the file.
    """
    with _state_lock(config_path):
        current = read_state(config_path)
        if current is None:
            return False
        if current.get("pid") != pid:
            return False
        current_created = current.get("created")
        if created:
            if current_created != created:
                return False
        elif isinstance(current_created, str) and current_created:
            return False
        path = state_path(config_path)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True


@contextmanager
def _state_lock(config_path: Path) -> Iterator[None]:
    lock_path = state_dir(config_path) / f"{config_path.resolve().name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("a+b")
    try:
        _lock_file(fh)
        yield
    finally:
        try:
            _unlock_file(fh)
        except OSError:
            pass
        fh.close()


def _lock_file(fh: Any) -> None:
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    if fh.seek(0, os.SEEK_END) == 0:
        fh.write(b"\0")
        fh.flush()
    while True:
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError("could not lock Team launch state")
            time.sleep(0.05)


def _unlock_file(fh: Any) -> None:
    if sys.platform == "win32":
        import msvcrt

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
