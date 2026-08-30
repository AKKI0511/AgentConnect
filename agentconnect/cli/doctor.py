"""CLI diagnostics for a Team file and a running Runtime."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Optional

import typer

from agentconnect.cli.client import RuntimeClient
from agentconnect.cli.state import read_state
from agentconnect.config.loaders import find_config_file, load_team_config
from agentconnect.team.errors import TeamError


def _has_any_provider_key() -> bool:
    for var in (
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
    ):
        if os.environ.get(var):
            return True
    return False


def _team_url(root: Path, explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit.rstrip("/")
    state = read_state(root)
    if state and isinstance(state.get("url"), str):
        return str(state["url"]).rstrip("/")
    try:
        config = load_team_config(start=root)
    except (FileNotFoundError, ValueError):
        return None
    return f"http://{config.host}:{config.port}"


def doctor(*, url: Optional[str] = None) -> None:
    """Print a short setup report and hints."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    root = Path.cwd()
    typer.echo(f"Python: {platform.python_version()}")
    has_key = _has_any_provider_key()
    typer.echo(f"LLM key present: {'yes' if has_key else 'no'}")

    config_path = find_config_file(root)
    if config_path is None:
        typer.echo("agentconnect.yaml: not found")
        typer.echo("hint: run 'agentconnect init' to scaffold a Team")
    else:
        try:
            config = load_team_config(config_path)
            typer.echo(f"agentconnect.yaml: valid ({config.team})")
        except ValueError as exc:
            typer.echo(f"agentconnect.yaml: invalid ({exc})")
            raise typer.Exit(code=1)

    origin = _team_url(root, url)
    if origin is None:
        typer.echo("runtime: not running")
        typer.echo("hint: run 'agentconnect up' in this directory")
        return
    try:
        with RuntimeClient(origin, timeout=3.0) as client:
            snapshot = client.status()
        typer.echo(
            f"runtime @ {origin}: {snapshot.get('team_name')} "
            f"({len(snapshot.get('members') or [])} members)"
        )
    except TeamError as exc:
        typer.echo(f"runtime @ {origin}: {exc.code}")
        typer.echo("hint: start the Team with 'agentconnect up'")
    except Exception:
        typer.echo(f"runtime @ {origin}: unreachable")
        typer.echo("hint: start the Team with 'agentconnect up'")
