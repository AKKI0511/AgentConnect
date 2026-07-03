from __future__ import annotations

from typing import Optional, Annotated

import httpx
import typer

from agentconnect.config import load_settings


def _normalize_base_url(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def ping(
    base_url: Annotated[
        Optional[str],
        typer.Option(
            "--base-url",
            help="Registry base URL; defaults to agentconnect.yaml clients.registry.base_url",
        ),
    ] = None,
    timeout: Annotated[float, typer.Option("--timeout", help="Timeout seconds")] = 3.0,
) -> None:
    """Check registry health endpoint and exit 0 if healthy, non-zero otherwise."""
    settings = load_settings()
    resolved = base_url or settings.clients.registry.base_url
    if not resolved:
        typer.echo(
            "Registry base URL not configured. Set clients.registry.base_url in agentconnect.yaml or pass --base-url."
        )
        raise typer.Exit(code=2)

    url = _normalize_base_url(resolved) + "health"

    message: str
    code: int
    try:
        resp = httpx.get(url, timeout=timeout)
        if resp.status_code == 200:
            try:
                status = resp.json().get("status")
            except Exception:
                status = None
            if status == "healthy":
                message, code = "healthy", 0
            else:
                message, code = "unhealthy", 3
        else:
            message, code = "unhealthy", 3
    except httpx.RequestError:
        message, code = "unreachable", 4
    except Exception:
        message, code = "unhealthy", 3

    typer.echo(message)
    raise typer.Exit(code=code)
