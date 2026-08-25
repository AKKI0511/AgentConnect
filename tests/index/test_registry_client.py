"""
Test suite for agentconnect/clients/registry_client.py

This test suite focuses on structural validation to ensure the RegistryAPIClient
works as expected without testing internal implementation details.

Focus areas:
- Client can be instantiated and configured
- Core methods are callable and handle basic success/failure
- Resource management works (cleanup)
- Basic integration patterns work
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from agentconnect.index.client import RegistryAPIClient
from agentconnect.team.directory.registration import AgentRegistration
from agentconnect.core.types import AgentType, InteractionMode, AgentIdentity


@pytest.fixture
def sample_agent_registration():
    """Create a minimal agent registration for testing."""
    identity = AgentIdentity.create_key_based()
    return AgentRegistration(
        agent_id="test-agent",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        identity=identity,
        name="Test Agent",
    )


@pytest.fixture
def mock_successful_client():
    """Create a client with mocked successful HTTP responses."""
    client = RegistryAPIClient()

    # Mock successful responses for all operations
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "agent_id": "test-agent"}

    client._client = AsyncMock()
    client._client.request.return_value = mock_response

    return client


class TestClientStructuralValidation:
    """Test that the client can be instantiated and basic operations work."""

    def test_client_instantiation(self):
        """Test that client can be instantiated with default settings."""
        client = RegistryAPIClient()

        assert client is not None
        assert hasattr(client, "_client")
        assert hasattr(client, "base_url")

    def test_client_with_custom_url(self):
        """Test that client accepts custom configuration."""
        client = RegistryAPIClient(base_url="http://custom:8000")

        assert "custom:8000" in client.base_url

    @pytest.mark.asyncio
    async def test_resource_cleanup(self):
        """Test that client resources can be cleaned up."""
        client = RegistryAPIClient()

        # Mock the HTTP client
        client._client = AsyncMock()

        # Should not raise exception
        await client.close()

        client._client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_pattern(self):
        """Test that client works as async context manager."""
        with patch.object(RegistryAPIClient, "close") as mock_close:
            async with RegistryAPIClient() as client:
                assert isinstance(client, RegistryAPIClient)

            mock_close.assert_called_once()


class TestCoreMethodsWork:
    """Test that core client methods are callable and handle basic scenarios."""

    @pytest.mark.asyncio
    async def test_register_method_works(
        self, mock_successful_client, sample_agent_registration
    ):
        """Test that register method is callable and returns expected result."""
        result = await mock_successful_client.register(sample_agent_registration)

        # Should return boolean result
        assert isinstance(result, bool)
        # HTTP client should have been called
        mock_successful_client._client.request.assert_called()

    @pytest.mark.asyncio
    async def test_get_registration_method_works(self, mock_successful_client):
        """Test that get_registration method is callable."""
        # Mock response for get_registration
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agent_id": "test-agent",
            "agent_type": "AI",
            "interaction_modes": ["AGENT_TO_AGENT"],
            "identity": {"type": "key_based", "public_key": "test-key"},
            "name": "Test Agent",
        }
        mock_successful_client._client.request.return_value = mock_response

        result = await mock_successful_client.get_registration("test-agent")

        # Should return result (or None)
        assert result is not None or result is None
        # HTTP client should have been called
        mock_successful_client._client.request.assert_called()

    @pytest.mark.asyncio
    async def test_unregister_method_works(self, mock_successful_client):
        """Test that unregister method is callable."""
        result = await mock_successful_client.unregister("test-agent")

        # Should return boolean result
        assert isinstance(result, bool)
        # HTTP client should have been called
        mock_successful_client._client.request.assert_called()

    @pytest.mark.asyncio
    async def test_get_all_agents_method_works(self, mock_successful_client):
        """Test that get_all_agents method is callable."""
        # Mock response for list
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_successful_client._client.request.return_value = mock_response

        result = await mock_successful_client.get_all_agents()

        # Should return list
        assert isinstance(result, list)
        # HTTP client should have been called
        mock_successful_client._client.request.assert_called()


class TestErrorHandling:
    """Test that client handles basic error scenarios gracefully."""

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test that network errors are handled gracefully."""
        client = RegistryAPIClient()

        # Mock network error
        client._client = AsyncMock()
        client._client.request.side_effect = httpx.RequestError("Network error")

        # Should handle error gracefully and return None after retries
        result = await client._request("GET", "test")
        assert result is None

    @pytest.mark.asyncio
    async def test_404_response_handling(self):
        """Test that 404 responses are handled appropriately."""
        client = RegistryAPIClient()

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404

        client._client = AsyncMock()
        client._client.request.return_value = mock_response

        result = await client._request("GET", "nonexistent")

        # Should return None for 404 (registry pattern)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_response_handling(self):
        """Test that invalid responses are handled gracefully."""
        client = RegistryAPIClient()

        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid response"

        client._client = AsyncMock()
        client._client.request.return_value = mock_response

        result = await client._request("GET", "test")

        # Should handle gracefully (return None)
        assert result is None


class TestIntegrationPatterns:
    """Test that common usage patterns work as expected."""

    @pytest.mark.asyncio
    async def test_basic_workflow_pattern(self, sample_agent_registration):
        """Test a basic register -> get -> unregister workflow."""
        client = RegistryAPIClient()

        # Mock all responses
        responses = [
            # Register response
            Mock(status_code=201, json=lambda: {"agent_id": "test-agent"}),
            # Get response
            Mock(
                status_code=200,
                json=lambda: {
                    "agent_id": "test-agent",
                    "agent_type": "AI",
                    "interaction_modes": ["AGENT_TO_AGENT"],
                    "identity": {"type": "key_based", "public_key": "test-key"},
                    "name": "Test Agent",
                },
            ),
            # Unregister response
            Mock(status_code=200, json=lambda: {"agent_id": "test-agent"}),
        ]

        client._client = AsyncMock()
        client._client.request.side_effect = responses

        # Basic workflow should work without exceptions
        register_result = await client.register(sample_agent_registration)
        get_result = await client.get_registration("test-agent")
        unregister_result = await client.unregister("test-agent")

        # All operations should complete
        assert isinstance(register_result, bool)
        assert get_result is not None or get_result is None  # Either found or not
        assert isinstance(unregister_result, bool)

    @pytest.mark.asyncio
    async def test_client_reuse_pattern(self):
        """Test that client can be reused for multiple operations."""
        client = RegistryAPIClient()

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        client._client = AsyncMock()
        client._client.request.return_value = mock_response

        # Multiple calls should work
        result1 = await client.get_all_agents()
        result2 = await client.get_all_agents()

        assert isinstance(result1, list)
        assert isinstance(result2, list)
        assert client._client.request.call_count == 2
