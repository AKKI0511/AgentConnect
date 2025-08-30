import subprocess
import sys


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agentconnect.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_registry_ping_unreachable() -> None:
    p = run_cli("registry", "ping", "--base-url", "http://127.0.0.1:59999")
    assert p.returncode != 0
    assert p.stdout.strip() == "unreachable"
