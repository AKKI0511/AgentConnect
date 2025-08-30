from __future__ import annotations

from typing import Optional, Annotated

import typer

from agentconnect.clients.registry_client import RegistryAPIClient
from agentconnect.mcp.registry_mcp_server import create_agent_discovery_mcp


def start_agent_discovery(
    registry_url: Annotated[
        Optional[str],
        typer.Option(
            "--registry-url",
            help="Override base URL for the Registry API (defaults to SDK config)",
        ),
    ] = None,
) -> None:
    """Start the Agent Discovery MCP server.

    Defaults come from agentconnect.yaml (mcp defaults and clients.registry.base_url).
    """
    client = RegistryAPIClient(base_url=registry_url) if registry_url else None
    mcp = create_agent_discovery_mcp(registry_client=client)
    mcp.run()
