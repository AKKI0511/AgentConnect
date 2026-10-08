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
    toml_path = tmp_path / "agentconnect.toml"
    assert toml_path.exists()
    text = toml_path.read_text(encoding="utf-8")
    assert "demo-team" in text
    assert "[tool.agentconnect]" in text
    assert "agents.assistant:create_assistant" in text
    assert "tools.shared:ping" in text
    assistant = tmp_path / "agents" / "assistant.py"
    assert assistant.exists()
    source = assistant.read_text(encoding="utf-8")
    assert "class Assistant" in source
    assert "def create_assistant" in source
    assert "MailboxMessage" in source
    assert "AgentProfile" in source
    shared = tmp_path / "tools" / "shared.py"
    assert shared.exists()
    assert "def ping" in shared.read_text(encoding="utf-8")

    p = run_cli("init", cwd=tmp_path)
    assert p.returncode == 1


def test_token_help() -> None:
    p = run_cli("token", "--help")
    assert p.returncode == 0
    assert "issue" in p.stdout
    assert "revoke" in p.stdout


def test_status_rejects_malformed_team_file(tmp_path: Path) -> None:
    (tmp_path / "agentconnect.toml").write_text("team = [\n", encoding="utf-8")
    p = run_cli("status", cwd=tmp_path)
    assert p.returncode == 1
    combined = p.stdout + p.stderr
    assert "invalid TOML" in combined


def test_doctor_without_team_file(tmp_path: Path) -> None:
    p = run_cli("doctor", cwd=tmp_path)
    assert p.returncode == 0
    assert "Team file: not found" in p.stdout


def test_init_preserves_existing_pyproject_team(tmp_path: Path) -> None:
    from agentconnect.config.loaders import dump_team_toml, load_team_config
    from agentconnect.config.models import TeamConfig

    (tmp_path / "pyproject.toml").write_text(
        dump_team_toml(TeamConfig(team="existing")),
        encoding="utf-8",
    )
    p = run_cli("init", cwd=tmp_path)
    assert p.returncode == 1
    combined = p.stdout + p.stderr
    assert "already exists" in combined
    assert "agentconnect up" in combined
    assert not (tmp_path / "agentconnect.toml").exists()
    assert load_team_config(start=tmp_path).team == "existing"


def test_malformed_pyproject_is_concise(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.agentconnect\n", encoding="utf-8")
    for command in (("doctor",), ("up",), ("status",)):
        p = run_cli(*command, cwd=tmp_path)
        assert p.returncode == 1
        combined = p.stdout + p.stderr
        assert "Traceback" not in combined
        assert len(combined) < 2000
        assert "invalid TOML" in combined or "Team file" in combined


def test_factory_runtime_error_is_concise(tmp_path: Path) -> None:
    from agentconnect.config.loaders import dump_team_toml
    from agentconnect.config.models import HostedAgentConfig, TeamConfig

    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "agents" / "broken.py").write_text(
        "def create_broken(name: str):\n    raise RuntimeError('model setup failed')\n",
        encoding="utf-8",
    )
    (tmp_path / "agentconnect.toml").write_text(
        dump_team_toml(
            TeamConfig(
                team="demo",
                embeddings="none",
                agents=[
                    HostedAgentConfig(
                        class_path="agents.broken:create_broken", name="broken"
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    p = run_cli("up", cwd=tmp_path)
    combined = p.stdout + p.stderr
    assert p.returncode != 0
    assert "Traceback" not in combined
    assert len(combined) < 2000
    assert "model setup failed" in combined
    assert "agentconnect.toml" in combined
    assert "agents.broken:create_broken" in combined


def test_missing_explicit_file_does_not_use_state(tmp_path: Path) -> None:
    from agentconnect.cli.state import write_state

    write_state(
        tmp_path / "agentconnect.toml",
        pid=1,
        url="http://127.0.0.1:9876",
        team="stale",
        created="test",
    )
    missing = tmp_path / "other.toml"
    p = run_cli("status", "--file", str(missing), cwd=tmp_path)
    assert p.returncode == 1
    combined = p.stdout + p.stderr
    assert "9876" not in combined
    assert "not found" in combined.lower()
