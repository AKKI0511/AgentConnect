"""Identify and stop the Team process recorded by ``agentconnect up``.

Ownership is a matching start-time token. Missing or unreadable identity
fails closed: it never authorizes a kill, and it is not treated as a
proven-dead process.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal, Optional

_VERIFY_WAIT_SECONDS = 3.0

ProcessStatus = Literal["dead", "live", "unknown"]


_TERMINAL_STATES = frozenset({"Z", "X", "x"})


def inspect_process(pid: int) -> tuple[ProcessStatus, Optional[str]]:
    """Return whether ``pid`` is dead, live, or unreadable, plus a token.

    ``dead`` means the PID is gone or is a terminated zombie that has not
    been reaped yet. ``live`` includes a start-time token. ``unknown``
    means the query failed or the token could not be read; it is not
    proof that the process has exited.
    """
    if not isinstance(pid, int) or pid <= 0:
        return "dead", None
    if sys.platform == "win32":
        return _windows_inspect(pid)
    return _posix_inspect(pid)


def process_exists(pid: int) -> bool:
    """Return True when ``pid`` is live and its identity could be read."""
    status, _token = inspect_process(pid)
    return status == "live"


def process_is_dead(pid: int) -> bool:
    """Return True only when ``pid`` is proven gone."""
    status, _token = inspect_process(pid)
    return status == "dead"


def process_created_token(pid: int) -> Optional[str]:
    """Return an opaque start-time token, or None when it cannot be read.

    Matching tokens mean the PID still names the same process. A mismatch
    means the PID was reused. None is not proof that the process is dead.
    """
    status, token = inspect_process(pid)
    if status == "live":
        return token
    return None


def is_owned_team_process(state: dict[str, Any], config_path: Path) -> bool:
    """Return True when ``state`` still names the Team process we started.

    Requires a recorded creation token and a matching live identity.
    Command-line text is not used. ``config_path`` is accepted for callers
    that already have the selected Team file.
    """
    _ = config_path
    pid = state.get("pid")
    recorded = state.get("created")
    if not isinstance(pid, int) or not isinstance(recorded, str) or not recorded:
        return False
    status, live = inspect_process(pid)
    return status == "live" and live == recorded


def terminate_pid(pid: int) -> None:
    """Stop ``pid`` and wait until it is gone.

    Raises:
        RuntimeError: The process could not be stopped.
    """
    if sys.platform == "win32":
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = (
                completed.stderr or completed.stdout or str(completed.returncode)
            ).strip()
            raise RuntimeError(
                f"could not stop pid {pid}: {detail or 'taskkill failed'}"
            )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError as exc:
            raise RuntimeError(f"could not stop pid {pid}: {exc}") from exc
    if _wait_until_gone(pid, _VERIFY_WAIT_SECONDS):
        return
    if sys.platform != "win32":
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError as exc:
            raise RuntimeError(f"could not stop pid {pid}: {exc}") from exc
        if _wait_until_gone(pid, 1.0):
            return
    raise RuntimeError(f"pid {pid} is still running")


def _wait_until_gone(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process_is_dead(pid):
            return True
        time.sleep(0.05)
    return process_is_dead(pid)


def _posix_inspect(pid: int) -> tuple[ProcessStatus, Optional[str]]:
    parsed = _read_proc_stat(pid)
    if parsed is not None:
        state, token = parsed
        if state in _TERMINAL_STATES:
            return "dead", None
        exists = _posix_exists(pid)
        if exists is False:
            return "dead", None
        if exists is None:
            return "unknown", None
        if token:
            return "live", token
        return "unknown", None
    exists = _posix_exists(pid)
    if exists is False:
        return "dead", None
    if exists is None:
        return "unknown", None
    state, token = _ps_state_and_start(pid)
    if state in _TERMINAL_STATES:
        return "dead", None
    if token:
        return "live", token
    exists = _posix_exists(pid)
    if exists is False:
        return "dead", None
    return "unknown", None


def _posix_exists(pid: int) -> Optional[bool]:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _read_proc_stat(pid: int) -> Optional[tuple[str, str]]:
    proc = Path(f"/proc/{pid}/stat")
    try:
        if not proc.is_file():
            return None
        data = proc.read_text(encoding="utf-8")
    except OSError:
        return None
    return _parse_proc_stat(data)


def _parse_proc_stat(data: str) -> Optional[tuple[str, str]]:
    rparen = data.rfind(")")
    if rparen < 0:
        return None
    fields = data[rparen + 2 :].split()
    if len(fields) < 20:
        return None
    state = fields[0]
    if not state:
        return None
    return state[0], fields[19]


def _ps_state_and_start(pid: int) -> tuple[Optional[str], Optional[str]]:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat=", "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None, None
    text = completed.stdout.strip()
    if not text:
        return None, None
    parts = text.split(None, 1)
    state = parts[0][:1] if parts else None
    started = parts[1].strip() if len(parts) > 1 else None
    return state or None, started or None


def _windows_inspect(pid: int) -> tuple[ProcessStatus, Optional[str]]:
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    process_query_limited = 0x1000
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL

    still_active = 259
    handle = kernel32.OpenProcess(process_query_limited, False, pid)
    if handle:
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return "unknown", None
            if exit_code.value != still_active:
                return "dead", None
            created = FILETIME()
            exited = FILETIME()
            kernel = FILETIME()
            user = FILETIME()
            ok = kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
            if not ok:
                return "unknown", None
            token = f"{created.dwHighDateTime:08x}{created.dwLowDateTime:08x}"
            return "live", token
        finally:
            kernel32.CloseHandle(handle)
    # ERROR_INVALID_PARAMETER (87): the PID does not name a process.
    if ctypes.get_last_error() == 87:
        return "dead", None
    return "unknown", None
