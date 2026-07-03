from __future__ import annotations

import os
from typing import Optional

import typer

from agentconnect.config import load_settings
from .registry import _normalize_base_url


def _has_any_provider_key() -> bool:
    for var in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
    ):
        if os.environ.get(var):
            return True
    return False


def _check_registry_health(base_url: str, timeout: float = 2.0) -> Optional[bool]:
    try:
        import httpx

        url = _normalize_base_url(base_url) + "health"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
        return resp.status_code == 200 and resp.json().get("status") == "healthy"
    except Exception:
        return None


def doctor() -> None:
    """Print concise diagnostic summary with hints."""
    import platform

    # Load .env from current working directory so provider keys in .env are recognized
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass

    py = platform.python_version()
    has_key = _has_any_provider_key()
    cfg_path = "agentconnect.yaml" if (os.path.exists("agentconnect.yaml")) else None
    settings = load_settings()
    base_url = settings.clients.registry.base_url
    health = _check_registry_health(base_url) if base_url else None

    typer.echo(f"Python: {py}")
    typer.echo(f"LLM key present: {'yes' if has_key else 'no'}")
    typer.echo(f"agentconnect.yaml: {'found' if cfg_path else 'not found'}")
    if base_url:
        status = (
            "healthy" if health else ("unreachable" if health is None else "unhealthy")
        )
        typer.echo(f"registry @ {base_url}: {status}")
    else:
        typer.echo("registry: base_url not configured")

    if not has_key:
        typer.echo(
            "hint: set one of OPENAI_API_KEY/ANTHROPIC_API_KEY/GROQ_API_KEY/GOOGLE_API_KEY"
        )
    if not cfg_path:
        typer.echo("hint: run 'agentconnect config init' to create agentconnect.yaml")
    if base_url and health is None:
        typer.echo(
            "hint: ensure registry server is running or update clients.registry.base_url"
        )
