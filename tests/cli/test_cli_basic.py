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


def test_help_smoke() -> None:
    p = run_cli("--help")
    assert p.returncode == 0
    assert "AgentConnect CLI" in p.stdout


def test_version() -> None:
    p = run_cli("version")
    assert p.returncode == 0
    assert p.stdout.strip()  # prints version


def test_config_help() -> None:
    p = run_cli("config", "--help")
    assert p.returncode == 0
    assert "init" in p.stdout and "show" in p.stdout and "validate" in p.stdout
