"""CLI diagnostics for a Team file, selected origin, and Runtime access."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from agentconnect.cli.client import RuntimeClient
from agentconnect.cli.origin import resolve_runtime_origin
from agentconnect.config.loaders import (
    find_config_file,
    load_selected_team,
    load_team_config,
)
from agentconnect.team.errors import TeamError


def _short(exc: BaseException, *, limit: int = 400) -> str:
    text = str(exc).strip() or type(exc).__name__
    text = " ".join(part.strip() for part in text.splitlines() if part.strip())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def doctor(*, url: Optional[str] = None, file: Optional[Path] = None) -> None:
    """Print a short setup report for the Team file and Runtime."""
    root = Path.cwd()

    config_path: Path | None = None
    try:
        if file is not None:
            config_path, config = load_selected_team(file, start=root)
            typer.echo(f"Team file {config_path.name}: valid ({config.team})")
        else:
            config_path = find_config_file(root)
            if config_path is None:
                typer.echo("Team file: not found")
                typer.echo("hint: run 'agentconnect init' to scaffold a Team")
            else:
                config = load_team_config(config_path)
                typer.echo(f"Team file {config_path.name}: valid ({config.team})")
    except FileNotFoundError as exc:
        typer.echo(f"Team file: {_short(exc)}")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        typer.echo(f"Team file: invalid ({_short(exc)})")
        raise typer.Exit(code=1) from None

    try:
        origin = resolve_runtime_origin(url=url, file=file, start=root)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"runtime: {_short(exc)}")
        raise typer.Exit(code=1) from None

    if url is None and file is None and config_path is None:
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
