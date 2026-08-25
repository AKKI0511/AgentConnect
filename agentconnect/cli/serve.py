from __future__ import annotations

import importlib
from typing import Optional, Annotated

import typer


def _missing_servers_extras_message() -> str:
    return (
        "Could not import the registry server. FastAPI and uvicorn are core "
        "dependencies; reinstall the package and see agentconnect/index/README.md."
    )


def registry(
    host: Annotated[
        Optional[str], typer.Option("--host", help="Override server host")
    ] = None,
    port: Annotated[
        Optional[int], typer.Option("--port", help="Override server port")
    ] = None,
    reload: Annotated[
        bool, typer.Option("--reload", is_flag=True, help="Enable auto-reload")
    ] = False,
) -> None:
    """Start the Registry API server (FastAPI) using env-only settings.

    Only host/port/reload flags are supported as convenience overrides; all deeper
    configuration is via environment variables (AGENTCONNECT_REGISTRY_*).
    """
    try:
        uvicorn = importlib.import_module("uvicorn")
        servers_cfg = importlib.import_module("agentconnect.config.servers")
        registry_server = importlib.import_module("agentconnect.index.service")
    except Exception:
        typer.echo(_missing_servers_extras_message())
        raise typer.Exit(code=1)

    # Resolve env-only defaults then apply CLI overrides
    settings = servers_cfg.RegistryAPISettings()
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port
    if reload:
        settings.reload = True

    app = registry_server.create_registry_api_app(settings)

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
