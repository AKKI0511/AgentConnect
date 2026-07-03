from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agentconnect.config import load_settings
from agentconnect.config.loaders import save_example_config, validate_config_file


def init(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing agentconnect.yaml if present.",
    ),
) -> None:
    """Generate agentconnect.yaml in the current directory.

    Non-interactive; fails if file exists unless --force is provided.
    """
    cfg_path = Path.cwd() / "agentconnect.yaml"
    if cfg_path.exists() and not force:
        typer.echo("agentconnect.yaml already exists. Use --force to overwrite.")
        raise typer.Exit(code=1)
    save_example_config(cfg_path)
    typer.echo(f"Wrote {cfg_path}")


def show() -> None:
    """Print the effective (redacted) settings from SDK config loader."""
    settings = load_settings()
    data = settings.model_dump_yaml_safe()
    # Prefer YAML if available, else JSON
    try:
        import yaml  # type: ignore

        typer.echo(yaml.safe_dump(data, sort_keys=False))
    except Exception:
        import json

        typer.echo(json.dumps(data, indent=2))


def validate(
    file: Annotated[Path, typer.Argument(..., exists=True, readable=True)],
) -> None:  # noqa: A002
    """Validate a YAML file against the SDK models; suitable for CI."""
    ok = validate_config_file(file)
    if ok:
        typer.echo("valid")
        raise typer.Exit(code=0)
    typer.echo("invalid")
    raise typer.Exit(code=1)
