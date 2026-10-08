"""Native process identity is fail-closed and uses OS start-time tokens."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from agentconnect.cli.process import (
    _SIGKILL,
    _parse_proc_stat,
    _posix_inspect,
    inspect_process,
    is_owned_team_process,
    process_is_dead,
    terminate_pid,
)


def _popen_sleeper() -> subprocess.Popen[bytes]:
    kwargs: dict[str, int] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def test_inspect_live_child_token_then_dead() -> None:
    proc = _popen_sleeper()
    token: str | None = None
    try:
        status, token = inspect_process(proc.pid)
        assert status == "live"
        assert token
        assert process_is_dead(proc.pid) is False
        owned = {"pid": proc.pid, "created": token}
        assert is_owned_team_process(owned, Path("unused.toml")) is True
        assert is_owned_team_process({"pid": proc.pid}, Path("unused.toml")) is False
        assert (
            is_owned_team_process(
                {"pid": proc.pid, "created": "nope"}, Path("unused.toml")
            )
            is False
        )
    finally:
        proc.kill()
        proc.wait(timeout=10)
    assert inspect_process(proc.pid)[0] == "dead"
    assert process_is_dead(proc.pid) is True
    if token:
        assert (
            is_owned_team_process(
                {"pid": proc.pid, "created": token}, Path("unused.toml")
            )
            is False
        )


def test_missing_created_token_is_never_owned() -> None:
    path = Path("unused.toml")
    assert is_owned_team_process({"pid": 1}, path) is False
    assert is_owned_team_process({"pid": 1, "created": ""}, path) is False


def test_parse_proc_stat_zombie_state() -> None:
    fields = "Z " + " ".join(str(index) for index in range(19))
    parsed = _parse_proc_stat(f"42 (python) {fields}")
    assert parsed == ("Z", "18")


def test_posix_inspect_treats_zombie_as_dead(monkeypatch) -> None:
    monkeypatch.setattr(
        "agentconnect.cli.process._read_proc_stat",
        lambda pid: ("Z", "12345"),
    )
    monkeypatch.setattr("agentconnect.cli.process._posix_exists", lambda pid: True)
    assert _posix_inspect(42) == ("dead", None)


def test_posix_inspect_unknown_when_identity_unreadable(monkeypatch) -> None:
    monkeypatch.setattr("agentconnect.cli.process._read_proc_stat", lambda pid: None)
    monkeypatch.setattr("agentconnect.cli.process._posix_exists", lambda pid: True)
    monkeypatch.setattr(
        "agentconnect.cli.process._ps_state_and_start",
        lambda pid: (None, None),
    )
    assert _posix_inspect(42) == ("unknown", None)


def test_killed_child_is_dead_before_parent_wait() -> None:
    proc = _popen_sleeper()
    try:
        assert inspect_process(proc.pid)[0] == "live"
        if sys.platform == "win32":
            proc.kill()
        else:
            os.kill(proc.pid, signal.SIGKILL)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if inspect_process(proc.pid)[0] == "dead":
                break
            time.sleep(0.02)
        assert inspect_process(proc.pid)[0] == "dead"
        stat_path = Path(f"/proc/{proc.pid}/stat")
        if stat_path.is_file():
            parsed = _parse_proc_stat(stat_path.read_text(encoding="utf-8"))
            assert parsed is not None
            assert parsed[0] == "Z"
    finally:
        proc.wait(timeout=10)


def test_terminate_pid_succeeds_before_parent_wait() -> None:
    proc = _popen_sleeper()
    try:
        status, token = inspect_process(proc.pid)
        assert status == "live"
        assert token
        terminate_pid(proc.pid, token)
        assert inspect_process(proc.pid)[0] == "dead"
    finally:
        proc.wait(timeout=10)


def test_terminate_pid_skips_sigkill_after_pid_reuse(monkeypatch) -> None:
    signals: list[int] = []
    current = ["orig"]

    def fake_inspect(pid: int) -> tuple[str, str | None]:
        return "live", current[0]

    def fake_kill(pid: int, sig: int) -> None:
        signals.append(sig)
        if sig == signal.SIGTERM:
            current[0] = "other"

    monkeypatch.setattr("agentconnect.cli.process.sys.platform", "linux")
    monkeypatch.setattr("agentconnect.cli.process.inspect_process", fake_inspect)
    monkeypatch.setattr("agentconnect.cli.process.os.kill", fake_kill)
    terminate_pid(4242, "orig")
    assert signals == [signal.SIGTERM]


def test_terminate_pid_sends_sigkill_when_same_process_stays_live(monkeypatch) -> None:
    signals: list[int] = []
    current_status = ["live"]

    def fake_inspect(pid: int) -> tuple[str, str | None]:
        if current_status[0] == "live":
            return "live", "orig"
        return "dead", None

    def fake_kill(pid: int, sig: int) -> None:
        signals.append(sig)
        if sig == _SIGKILL:
            current_status[0] = "dead"

    clock = {"t": 0.0}

    def monotonic() -> float:
        return clock["t"]

    def sleep(seconds: float) -> None:
        clock["t"] += seconds

    monkeypatch.setattr("agentconnect.cli.process.sys.platform", "linux")
    monkeypatch.setattr("agentconnect.cli.process.inspect_process", fake_inspect)
    monkeypatch.setattr("agentconnect.cli.process.os.kill", fake_kill)
    monkeypatch.setattr("agentconnect.cli.process.time.monotonic", monotonic)
    monkeypatch.setattr("agentconnect.cli.process.time.sleep", sleep)
    terminate_pid(4242, "orig")
    assert signals == [signal.SIGTERM, _SIGKILL]


def test_terminate_pid_no_signal_when_token_already_mismatched(monkeypatch) -> None:
    signals: list[int] = []
    monkeypatch.setattr("agentconnect.cli.process.sys.platform", "linux")
    monkeypatch.setattr(
        "agentconnect.cli.process.inspect_process", lambda pid: ("live", "other")
    )
    monkeypatch.setattr(
        "agentconnect.cli.process.os.kill",
        lambda pid, sig: signals.append(sig),
    )
    terminate_pid(4242, "orig")
    assert signals == []
