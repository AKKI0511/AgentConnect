import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agentconnect.cli", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_help_lists_m8_commands() -> None:
    p = run_cli("--help")
    assert p.returncode == 0
    for name in (
        "init",
        "up",
        "down",
        "status",
        "token",
        "find",
        "ask",
        "trace",
        "watch",
        "doctor",
    ):
        assert name in p.stdout


def test_version() -> None:
    p = run_cli("version")
    assert p.returncode == 0
    assert p.stdout.strip()


def test_init_writes_team_file_and_agent(tmp_path: Path) -> None:
    p = run_cli("init", "--name", "demo-team", cwd=tmp_path)
    assert p.returncode == 0
    yaml_path = tmp_path / "agentconnect.yaml"
    assert yaml_path.exists()
    text = yaml_path.read_text(encoding="utf-8")
    assert "demo-team" in text
    assert "agents.assistant:Assistant" in text
    assistant = tmp_path / "agents" / "assistant.py"
    assert assistant.exists()
    assert "class Assistant" in assistant.read_text(encoding="utf-8")

    p = run_cli("init", cwd=tmp_path)
    assert p.returncode == 1


def test_token_help() -> None:
    p = run_cli("token", "--help")
    assert p.returncode == 0
    assert "issue" in p.stdout
    assert "revoke" in p.stdout


def test_doctor_without_yaml(tmp_path: Path) -> None:
    p = run_cli("doctor", cwd=tmp_path)
    assert p.returncode == 0
    assert "agentconnect.yaml: not found" in p.stdout
