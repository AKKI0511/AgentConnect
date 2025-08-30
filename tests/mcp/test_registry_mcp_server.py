"""
Test suite for agentconnect/mcp/registry_mcp_server.py

This test suite focuses on MCP integration layer validation to ensure the MCP server
works as expected without testing internal implementation details.

Focus areas:
- MCP tool interface compliance and protocol adherence
- Integration with health check and registry client works
- Basic error handling at the MCP layer
- Service availability checks
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from types import SimpleNamespace
from contextlib import asynccontextmanager

from agentconnect.mcp.registry_mcp_server import (
    create_agent_discovery_mcp,
    _check_registry_api_health,
)


class TestIntegrationLayer:
    """Test that MCP server integrates properly with underlying services."""

    @pytest.mark.asyncio
    async def test_factory_without_client_creates_client_and_lifespan_works(self):
        """Factory should work without DI and create a client inside lifespan."""
        captured = {}

        class DummyMCP:
            def __init__(self, *args, **kwargs):
                captured["lifespan"] = kwargs.get("lifespan")
            def add_tool(self, *_, **__):
                return None

        with patch("agentconnect.mcp.registry_mcp_server.FastMCP", new=DummyMCP), patch(
            "agentconnect.mcp.registry_mcp_server._check_registry_api_health",
            new=AsyncMock(return_value=True),
        ):
            _ = create_agent_discovery_mcp()

        lifespan = captured["lifespan"]
        assert lifespan is not None

        # Enter lifespan and verify registry_client exists on context
        @asynccontextmanager
        async def _use_lifespan():
            async with lifespan(SimpleNamespace()) as ctx:
                yield ctx

        async with _use_lifespan() as ctx:
            assert hasattr(ctx, "registry_client")
            assert isinstance(ctx.is_healthy, bool)

    @pytest.mark.asyncio
    async def test_factory_with_injected_client_uses_it(self):
        """Factory should use the provided registry_client in lifespan."""
        captured = {}

        class DummyMCP:
            def __init__(self, *args, **kwargs):
                captured["lifespan"] = kwargs.get("lifespan")
            def add_tool(self, *_, **__):
                return None

        injected_client = AsyncMock()
        injected_client.base_url = "http://localhost:8000"

        with patch("agentconnect.mcp.registry_mcp_server.FastMCP", new=DummyMCP), patch(
            "agentconnect.mcp.registry_mcp_server._check_registry_api_health",
            new=AsyncMock(return_value=True),
        ):
            _ = create_agent_discovery_mcp(registry_client=injected_client)

        lifespan = captured["lifespan"]
        assert lifespan is not None

        @asynccontextmanager
        async def _use_lifespan():
            async with lifespan(SimpleNamespace()) as ctx:
                yield ctx

        async with _use_lifespan() as ctx:
            # Same instance should be present
            assert getattr(ctx, "registry_client") is injected_client
            assert isinstance(ctx.is_healthy, bool)

    @pytest.mark.asyncio
    async def test_health_check_integration_works(self):
        """Test that health check function works as expected."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.get.return_value = mock_response

            result = await _check_registry_api_health("http://localhost:8000", 5.0)

            assert result is True
