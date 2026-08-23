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


def test_config_init_and_show_and_validate(tmp_path: Path) -> None:
    p = run_cli("config", "init", cwd=tmp_path)
    assert p.returncode == 0
    assert (tmp_path / "agentconnect.yaml").exists()

    p = run_cli("config", "show", cwd=tmp_path)
    assert p.returncode == 0
    assert "clients" in p.stdout

    p = run_cli("config", "validate", str(tmp_path / "agentconnect.yaml"), cwd=tmp_path)
    assert p.returncode == 0
    assert "valid" in p.stdout
