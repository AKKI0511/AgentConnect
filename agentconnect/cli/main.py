from __future__ import annotations

import typer

from agentconnect import __version__

# Subcommand implementations
from . import config as config_cmds
from . import registry as registry_cmds
from . import serve as serve_cmds
from . import doctor as doctor_cmds


app = typer.Typer(no_args_is_help=True, add_completion=False, help="AgentConnect CLI")


@app.command("version")
def version() -> None:
    """Print AgentConnect version."""
    typer.echo(f"{__version__}")


# config group
config_app = typer.Typer(
    no_args_is_help=True, add_completion=False, help="Configuration commands"
)
config_app.command("init")(config_cmds.init)
config_app.command("show")(config_cmds.show)
config_app.command("validate")(config_cmds.validate)
app.add_typer(config_app, name="config")


# serve group
serve_app = typer.Typer(
    no_args_is_help=True, add_completion=False, help="Server commands"
)
serve_app.command("registry")(serve_cmds.registry)
app.add_typer(serve_app, name="serve")


# registry group
registry_app = typer.Typer(
    no_args_is_help=True, add_completion=False, help="Registry utilities"
)
registry_app.command("ping")(registry_cmds.ping)
app.add_typer(registry_app, name="registry")


@app.command("doctor")
def doctor() -> None:
    """Run quick diagnostics and print concise status summary."""
    doctor_cmds.doctor()


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
