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
from unittest.mock import AsyncMock, Mock, patch

from agentconnect.mcp.registry_mcp_server import (
    search_for_agents_tool,
    check_registry_api_health,
)
from mcp.server.fastmcp import Context


@pytest.fixture
def mock_context():
    """Create a mock MCP Context."""
    context = Mock(spec=Context)
    context.debug = AsyncMock()
    context.error = AsyncMock()
    
    # Mock the nested attribute access for lifespan_context
    app_context_mock = Mock()
    app_context_mock.is_healthy = True
    context.request_context.lifespan_context = app_context_mock
    
    return context


@pytest.fixture
def mock_successful_setup():
    """Create mocks for successful MCP operation."""
    with patch('agentconnect.mcp.registry_mcp_server.check_registry_api_health') as mock_health, \
         patch('agentconnect.mcp.registry_mcp_server.RegistryAPIClient') as mock_client_class:
        
        # Setup successful health check
        mock_health.return_value = True
        
        # Setup successful client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.get_by_capability_semantic.return_value = []
        
        yield mock_health, mock_client_class, mock_client


class TestMCPToolInterface:
    """Test that MCP tool interface works and complies with protocol."""

    @pytest.mark.asyncio
    async def test_mcp_tool_returns_correct_format(self, mock_context, mock_successful_setup):
        """Test that MCP tool returns the expected response format."""
        _, _, _ = mock_successful_setup
        
        result = await search_for_agents_tool(
            ctx=mock_context,
            query="test query"
        )
        
        # Verify MCP protocol compliance
        assert isinstance(result, dict), "MCP tool must return dict"
        assert "message" in result, "Response must have 'message' field"
        assert "results" in result, "Response must have 'results' field"
        assert isinstance(result["results"], list), "Results must be a list"

    @pytest.mark.asyncio
    async def test_parameter_validation(self, mock_context):
        """Test that invalid parameters are handled appropriately."""
        # Test invalid output_detail parameter
        result = await search_for_agents_tool(
            ctx=mock_context,
            query="test query",
            output_detail="invalid_level"
        )
        
        # Should return error in MCP format
        assert isinstance(result, dict)
        assert "Invalid output_detail" in result["message"]
        assert result["results"] == []


class TestIntegrationLayer:
    """Test that MCP server integrates properly with underlying services."""

    @pytest.mark.asyncio
    async def test_health_check_integration_works(self):
        """Test that health check function works as expected."""
        with patch('agentconnect.mcp.registry_mcp_server.registry_settings') as mock_settings, \
             patch('httpx.AsyncClient') as mock_client_class:
            
            # Setup mocks
            mock_settings.api.host = "localhost"
            mock_settings.api.port = 8000
            
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.get.return_value = mock_response
            
            result = await check_registry_api_health()
            
            # Should return success
            assert result is True

    @pytest.mark.asyncio
    async def test_registry_client_integration_works(self, mock_context, mock_successful_setup):
        """Test that registry client integration works properly."""
        mock_health, _, mock_client = mock_successful_setup
        
        # Since the client is part of the lifespan, we need to mock it on the app context
        mock_context.request_context.lifespan_context.registry_client = mock_client
        
        await search_for_agents_tool(
            ctx=mock_context,
            query="test query"
        )
        
        # Verify integration points
        mock_client.get_by_capability_semantic.assert_called_once()  # Client method called


class TestErrorHandling:
    """Test that MCP layer handles error scenarios gracefully."""

    @pytest.mark.asyncio
    async def test_service_unavailable_handling(self, mock_context):
        """Test that service unavailable is handled gracefully."""
        # Unset the healthy flag on the mock context
        mock_context.request_context.lifespan_context.is_healthy = False
        
        with patch('agentconnect.mcp.registry_mcp_server.check_registry_api_health') as mock_health:
            
            # Health check fails on re-check
            mock_health.return_value = False
            
            result = await search_for_agents_tool(
                ctx=mock_context,
                query="test query"
            )
            
            # Should return appropriate error without crashing
            assert isinstance(result, dict)
            assert "Registry API server is not running" in result["message"]
            assert result["results"] == []
            
            # Check that health check was re-attempted
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_error_handling(self, mock_context):
        """Test that client errors are handled gracefully."""
        with patch('agentconnect.mcp.registry_mcp_server.check_registry_api_health') as mock_health, \
             patch('agentconnect.mcp.registry_mcp_server.RegistryAPIClient') as mock_client_class:
            
            mock_health.return_value = True
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.get_by_capability_semantic.side_effect = Exception("Client error")
            
            # Since the client is part of the lifespan, we need to mock it on the app context
            mock_context.request_context.lifespan_context.registry_client = mock_client
            
            result = await search_for_agents_tool(
                ctx=mock_context,
                query="test query"
            )
            
            # Should handle error gracefully
            assert isinstance(result, dict)
            assert "Error searching for agents" in result["message"]
            assert result["results"] == []


class TestBasicWorkflow:
    """Test that basic MCP workflow patterns work as expected."""

    @pytest.mark.asyncio
    async def test_successful_search_workflow(self, mock_context, mock_successful_setup):
        """Test that a successful search workflow completes properly."""
        _, _, mock_client = mock_successful_setup
        
        # Since the client is part of the lifespan, we need to mock it on the app context
        mock_context.request_context.lifespan_context.registry_client = mock_client
        
        # Should complete without exceptions
        result = await search_for_agents_tool(
            ctx=mock_context,
            query="data analysis",
            top_k=3,
            strictness=0.3,
            output_detail="summary"
        )
        
        # Should return valid result
        assert isinstance(result, dict)
        assert "message" in result
        assert "results" in result
        assert isinstance(result["results"], list)
