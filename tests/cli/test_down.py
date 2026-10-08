"""Shutdown ownership, failed stop, and per-configuration state."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from agentconnect.cli.main import _run_up, app
from agentconnect.cli.process import inspect_process, is_owned_team_process
from agentconnect.cli.state import (
    clear_owned_state,
    publish_state,
    read_state,
    state_path,
    write_state,
)
from agentconnect.config.loaders import dump_team_toml, load_selected_team
from agentconnect.config.models import TeamConfig
from tests.cli.test_cli import run_cli


def _toml(path: Path, *, team: str, port: int = 9000) -> Path:
    path.write_text(
        dump_team_toml(
            TeamConfig(team=team, port=port, embeddings="none", require_join_auth=True)
        ),
        encoding="utf-8",
    )
    return path


def test_failed_stop_keeps_state_and_is_nonzero(tmp_path: Path, monkeypatch) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config, pid=4242, url="http://127.0.0.1:9000", team="demo", created="t0"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agentconnect.cli.main.inspect_process", lambda pid: ("live", "t0")
    )
    monkeypatch.setattr(
        "agentconnect.cli.main.is_owned_team_process", lambda state, path: True
    )

    def boom(pid: int) -> None:
        raise RuntimeError("taskkill failed")

    monkeypatch.setattr("agentconnect.cli.main.terminate_pid", boom)
    result = CliRunner().invoke(app, ["down"])
    combined = result.stdout + result.output
    assert result.exit_code != 0
    assert "stopped" not in result.stdout
    assert "taskkill failed" in combined
    assert read_state(config) is not None
    assert state_path(config).is_file()


def test_reused_pid_is_not_killed(tmp_path: Path) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config,
        pid=os.getpid(),
        url="http://127.0.0.1:9000",
        team="demo",
        created="not-this-process",
    )
    result = run_cli("down", cwd=tmp_path)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "not killed" in combined
    assert read_state(config) is not None
    assert os.getpid() > 0


def test_dead_pid_clears_state(tmp_path: Path) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config, pid=4242, url="http://127.0.0.1:9000", team="demo", created="t0"
    )
    result = run_cli("down", cwd=tmp_path)
    assert result.returncode == 0
    assert "stopped" in result.stdout
    assert read_state(config) is None


def test_two_configs_have_separate_state(tmp_path: Path) -> None:
    first = _toml(tmp_path / "one.toml", team="one", port=9001)
    second = _toml(tmp_path / "two.toml", team="two", port=9002)
    write_state(first, pid=11, url="http://127.0.0.1:9001", team="one", created="a")
    write_state(second, pid=22, url="http://127.0.0.1:9002", team="two", created="b")
    result = run_cli("down", "--file", str(first), cwd=tmp_path)
    assert result.returncode == 0
    assert read_state(first) is None
    leftover = read_state(second)
    assert leftover is not None
    assert leftover["pid"] == 22


def test_nested_directory_stop_uses_parent_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "nested"
    nested.mkdir(parents=True)
    config = _toml(project / "agentconnect.toml", team="demo")
    write_state(
        config, pid=4242, url="http://127.0.0.1:9000", team="demo", created="t0"
    )
    result = run_cli("down", cwd=nested)
    assert result.returncode == 0
    assert read_state(config) is None


def test_duplicate_up_refuses_owned_process(tmp_path: Path, monkeypatch) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config,
        pid=4242,
        url="http://127.0.0.1:9555",
        team="demo",
        created="t0",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agentconnect.cli.main.is_owned_team_process", lambda state, path: True
    )
    result = CliRunner().invoke(app, ["up"])
    combined = result.stdout + result.output
    assert result.exit_code != 0
    assert "already running" in combined
    assert "9555" in combined
    assert read_state(config) is not None


def test_owned_requires_matching_created(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "agentconnect.toml"
    monkeypatch.setattr(
        "agentconnect.cli.process.inspect_process",
        lambda pid: ("live", "live"),
    )
    assert is_owned_team_process({"pid": 1, "created": "live"}, path) is True
    assert is_owned_team_process({"pid": 1, "created": "old"}, path) is False
    assert is_owned_team_process({"pid": 1}, path) is False
    assert is_owned_team_process({"pid": 1, "created": ""}, path) is False


def test_missing_created_token_does_not_authorize_stop(tmp_path: Path) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config,
        pid=os.getpid(),
        url="http://127.0.0.1:9000",
        team="demo",
        created="",
    )
    result = run_cli("down", cwd=tmp_path)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "cannot verify" in combined
    assert "stopped" not in result.stdout
    assert read_state(config) is not None
    assert os.getpid() > 0


def test_unreadable_identity_is_not_treated_as_dead(
    tmp_path: Path, monkeypatch
) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config, pid=4242, url="http://127.0.0.1:9000", team="demo", created="t0"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agentconnect.cli.main.inspect_process", lambda pid: ("unknown", None)
    )
    result = CliRunner().invoke(app, ["down"])
    combined = result.stdout + result.output
    assert result.exit_code != 0
    assert "cannot verify" in combined
    assert "stopped" not in result.stdout
    assert read_state(config) is not None


def test_clear_owned_state_does_not_remove_foreign_record(tmp_path: Path) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(
        config, pid=2, url="http://127.0.0.1:9000", team="demo", created="winner"
    )
    assert clear_owned_state(config, pid=1, created="loser") is False
    leftover = read_state(config)
    assert leftover is not None
    assert leftover["created"] == "winner"
    assert leftover["pid"] == 2


def test_publish_state_refuses_other_live_owner(tmp_path: Path, monkeypatch) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(config, pid=1, url="http://127.0.0.1:9000", team="demo", created="a")
    monkeypatch.setattr(
        "agentconnect.cli.state.inspect_process",
        lambda pid: ("live", "a"),
    )
    with pytest.raises(RuntimeError, match="already running"):
        publish_state(
            config,
            pid=2,
            url="http://127.0.0.1:9001",
            team="demo",
            created="b",
        )
    leftover = read_state(config)
    assert leftover is not None
    assert leftover["created"] == "a"


def test_publish_state_refuses_unreadable_owner(tmp_path: Path, monkeypatch) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(config, pid=1, url="http://127.0.0.1:9000", team="demo", created="a")
    monkeypatch.setattr(
        "agentconnect.cli.state.inspect_process",
        lambda pid: ("unknown", None),
    )
    with pytest.raises(RuntimeError, match="cannot verify"):
        publish_state(
            config,
            pid=2,
            url="http://127.0.0.1:9001",
            team="demo",
            created="b",
        )
    leftover = read_state(config)
    assert leftover is not None
    assert leftover["pid"] == 1
    assert leftover["created"] == "a"


def test_publish_state_refuses_missing_token_when_live(
    tmp_path: Path, monkeypatch
) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(config, pid=1, url="http://127.0.0.1:9000", team="demo", created="")
    monkeypatch.setattr(
        "agentconnect.cli.state.inspect_process",
        lambda pid: ("live", "now"),
    )
    with pytest.raises(RuntimeError, match="cannot verify"):
        publish_state(
            config,
            pid=2,
            url="http://127.0.0.1:9001",
            team="demo",
            created="b",
        )
    leftover = read_state(config)
    assert leftover is not None
    assert leftover["pid"] == 1
    assert "created" not in leftover


def test_publish_state_replaces_dead_or_reused_pid(tmp_path: Path, monkeypatch) -> None:
    config = _toml(tmp_path / "agentconnect.toml", team="demo")
    write_state(config, pid=1, url="http://127.0.0.1:9000", team="demo", created="old")
    monkeypatch.setattr(
        "agentconnect.cli.state.inspect_process",
        lambda pid: ("dead", None),
    )
    publish_state(
        config, pid=2, url="http://127.0.0.1:9001", team="demo", created="new"
    )
    replaced = read_state(config)
    assert replaced is not None
    assert replaced["pid"] == 2
    assert replaced["created"] == "new"

    write_state(config, pid=3, url="http://127.0.0.1:9000", team="demo", created="old")
    monkeypatch.setattr(
        "agentconnect.cli.state.inspect_process",
        lambda pid: ("live", "other"),
    )
    publish_state(
        config, pid=4, url="http://127.0.0.1:9002", team="demo", created="newer"
    )
    reused = read_state(config)
    assert reused is not None
    assert reused["pid"] == 4
    assert reused["created"] == "newer"


@pytest.mark.asyncio
async def test_failed_start_does_not_clear_foreign_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _toml(tmp_path / "agentconnect.toml", team="demo", port=9555)

    async def boom(self: object, *args: object, **kwargs: object) -> str:
        raise RuntimeError("bind failed")

    monkeypatch.setattr("agentconnect.team.runtime.Team.serve", boom)
    write_state(
        config_path,
        pid=999,
        url="http://127.0.0.1:9555",
        team="demo",
        created="winner",
    )
    _, config = load_selected_team(config_path, start=tmp_path)
    with pytest.raises(typer.Exit):
        await _run_up(config, config_path)
    leftover = read_state(config_path)
    assert leftover is not None
    assert leftover["created"] == "winner"
    assert leftover["pid"] == 999


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _popen_up(cwd: Path, config: Path) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {
        "args": [
            sys.executable,
            "-m",
            "agentconnect.cli",
            "up",
            "--file",
            str(config.resolve()),
        ],
        "cwd": str(cwd),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(**kwargs)


def _wait_live_state(config: Path, timeout: float = 25.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = read_state(config)
        if state and isinstance(state.get("pid"), int):
            status, token = inspect_process(int(state["pid"]))
            if status == "live" and token and token == state.get("created"):
                return state
        time.sleep(0.05)
    raise AssertionError("Team launch state did not become live")


def _kill_proc(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def test_real_up_down_roundtrip(tmp_path: Path) -> None:
    import httpx

    port = _free_port()
    config = _toml(tmp_path / "agentconnect.toml", team="demo", port=port)
    proc = _popen_up(tmp_path, config)
    try:
        state = _wait_live_state(config)
        origin = str(state["url"])
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{origin}/agentconnect/v1/status")
            assert response.status_code == 200
        result = run_cli("down", "--file", str(config), cwd=tmp_path)
        assert result.returncode == 0
        assert "stopped" in result.stdout
        assert read_state(config) is None
        proc.wait(timeout=15)
        assert proc.poll() is not None
        assert inspect_process(int(state["pid"]))[0] == "dead"
    except Exception:
        _kill_proc(proc)
        raise
    finally:
        _kill_proc(proc)


def test_concurrent_up_preserves_winner_state(tmp_path: Path) -> None:
    port = _free_port()
    config = _toml(tmp_path / "agentconnect.toml", team="demo", port=port)
    first = _popen_up(tmp_path, config)
    second = _popen_up(tmp_path, config)
    try:
        state = _wait_live_state(config)
        winner = int(state["pid"])
        created = state["created"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if first.poll() is not None or second.poll() is not None:
                time.sleep(0.2)
                break
            time.sleep(0.05)
        leftover = read_state(config)
        assert leftover is not None
        assert leftover["pid"] == winner
        assert leftover["created"] == created
        assert inspect_process(winner)[0] == "live"
        result = run_cli("down", "--file", str(config), cwd=tmp_path)
        assert result.returncode == 0
        assert read_state(config) is None
    finally:
        _kill_proc(first)
        _kill_proc(second)
