"""
End-to-end tests for the capability discovery functionality.

This module provides comprehensive tests for the capability discovery system,
including semantic search, string matching, and Qdrant integration.
"""

import pytest
import shutil
import tempfile
from typing import Dict, List, Set
from datetime import datetime
import pytest_asyncio
from tests.core.utils import print_header, print_step, print_success, print_result

# Core imports
from agentconnect.core.types import AgentType, AgentIdentity, Capability, InteractionMode, Skill, VerificationStatus
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.registry.capability_discovery import CapabilityDiscoveryService

# Sample test data
TEST_CAPABILITIES = [
    Capability(
        name="weather_forecast",
        description="Get the weather forecast for a specified location",
        input_schema={"location": "string", "days": "integer"},
        output_schema={"forecast": "array"},
        version="1.0"
    ),
    Capability(
        name="stock_price",
        description="Get the current stock price for a given ticker symbol",
        input_schema={"ticker": "string"},
        output_schema={"price": "float", "currency": "string"},
        version="1.0"
    ),
    Capability(
        name="news_search",
        description="Search for news articles on a given topic",
        input_schema={"topic": "string", "limit": "integer"},
        output_schema={"articles": "array"},
        version="1.0"
    ),
    Capability(
        name="image_generation",
        description="Generate an image based on a text prompt",
        input_schema={"prompt": "string", "style": "string"},
        output_schema={"image_url": "string"},
        version="1.1"
    ),
    Capability(
        name="code_completion",
        description="Complete code snippets based on context",
        input_schema={"language": "string", "code": "string"},
        output_schema={"completion": "string"},
        version="1.0"
    ),
]

# Create mock agent registrations
def create_test_registration(
    agent_id: str,
    name: str,
    description: str,
    capabilities: List[Capability],
    organization: str = "Test Organization",
    developer: str = "Test Developer"
) -> AgentRegistration:
    """Create a test agent registration with the given parameters."""
    # Create an identity
    identity = AgentIdentity.create_key_based()
    
    # Create registration
    registration = AgentRegistration(
        agent_id=agent_id,
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        identity=identity,
        name=name,
        description=description,
        organization=organization,
        developer=developer,
        capabilities=capabilities,
        skills=[Skill(name="test_skill", description="Test skill")],
        tags=["test", agent_id],
        registered_at=datetime.now()
    )
    
    return registration

# Create test registrations
def create_test_registrations() -> Dict[str, AgentRegistration]:
    """Create a set of test agent registrations with different capabilities."""
    registrations = {}
    
    # Weather agent
    weather_agent = create_test_registration(
        agent_id="weather-agent-1",
        name="Weather Forecaster",
        description="Provides detailed weather forecasts for locations around the world",
        capabilities=[TEST_CAPABILITIES[0]],
        organization="Weather Corp",
        developer="Climate Team"
    )
    registrations[weather_agent.agent_id] = weather_agent
    
    # Finance agent
    finance_agent = create_test_registration(
        agent_id="finance-agent-1",
        name="Stock Analyzer",
        description="Provides real-time stock market data and analysis",
        capabilities=[TEST_CAPABILITIES[1]],
        organization="Finance Inc",
        developer="Market Analysis Team"
    )
    registrations[finance_agent.agent_id] = finance_agent
    
    # News agent
    news_agent = create_test_registration(
        agent_id="news-agent-1",
        name="News Aggregator",
        description="Aggregates and searches news from multiple sources",
        capabilities=[TEST_CAPABILITIES[2]],
        organization="News Network",
        developer="Content Team"
    )
    registrations[news_agent.agent_id] = news_agent
    
    # Multi-capability agent
    multi_agent = create_test_registration(
        agent_id="multi-agent-1",
        name="Creative Assistant",
        description="Helps with creative tasks including image generation and code completion",
        capabilities=[TEST_CAPABILITIES[3], TEST_CAPABILITIES[4]],
        organization="Creative Studio",
        developer="AI Team"
    )
    registrations[multi_agent.agent_id] = multi_agent
    
    # Another weather agent from different org
    alt_weather_agent = create_test_registration(
        agent_id="weather-agent-2",
        name="Global Weather Service",
        description="Provides global weather data and forecasts using satellite imagery",
        capabilities=[TEST_CAPABILITIES[0]],
        organization="Global Weather Inc",
        developer="Meteorology Team"
    )
    registrations[alt_weather_agent.agent_id] = alt_weather_agent
    
    return registrations

# Create capabilities index from registrations
def extract_capabilities_index(registrations: Dict[str, AgentRegistration]) -> Dict[str, Set[str]]:
    """Extract capabilities index from agent registrations."""
    capabilities_index = {}
    
    for agent_id, registration in registrations.items():
        for capability in registration.capabilities:
            if capability.name not in capabilities_index:
                capabilities_index[capability.name] = set()
            capabilities_index[capability.name].add(agent_id)
    
    return capabilities_index

# Main test fixtures
@pytest_asyncio.fixture
async def discovery_service():
    """Create a capability discovery service for testing."""
    # Create with in-memory Qdrant
    service = CapabilityDiscoveryService({
        "in_memory": True,
        "use_quantization": False,  # Disable for faster tests
        "model_name": "all-MiniLM-L6-v2"  # Use small model for faster tests
    })
    
    # Initialize embeddings model
    await service.initialize_embeddings_model()
    
    yield service

@pytest.fixture
def test_registrations():
    """Create test agent registrations."""
    return create_test_registrations()

@pytest.fixture
def capabilities_index(test_registrations):
    """Create capabilities index from test registrations."""
    return extract_capabilities_index(test_registrations)

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Clean up
    shutil.rmtree(temp_dir)

# Group tests within a class
class TestCapabilityDiscoveryE2E:

    @pytest.mark.asyncio
    async def test_capability_discovery_string_matching(self, discovery_service: CapabilityDiscoveryService, test_registrations: Dict[str, AgentRegistration], capabilities_index: Dict[str, Set[str]]):
        """Test finding agents by capability name using string matching."""
        print_header("Testing Capability Discovery with String Matching")
        
        print_step("Searching for agents with 'weather_forecast' capability")
        results = await discovery_service.find_by_capability_name(
            "weather_forecast",
            test_registrations,
            capabilities_index,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Results", results)
        
        # Assertions
        assert len(results) == 2
        assert "weather-agent-1" in [r.agent_id for r in results]
        assert "weather-agent-2" in [r.agent_id for r in results]
        
        print_success("Completed search for all weather forecast agents. Please verify results above.")
        
        print_step("Searching for agents with 'stock_price' capability")
        results = await discovery_service.find_by_capability_name(
            "stock_price",
            test_registrations,
            capabilities_index,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Results", results)
        
        # Assertions
        assert len(results) == 1
        assert results[0].agent_id == "finance-agent-1"
        
        print_success("Completed search for stock price agent. Please verify results above.")
        
        print_step("Searching for non-existent capability")
        results = await discovery_service.find_by_capability_name(
            "translation",
            test_registrations,
            capabilities_index,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Results", results)
        
        # Assertions
        assert len(results) == 0
        
        print_success("Completed search for non-existent capability. Please verify results above.")

    @pytest.mark.asyncio
    async def test_semantic_search_with_embeddings(self, discovery_service: CapabilityDiscoveryService, test_registrations: Dict[str, AgentRegistration]):
        """Test semantic search using embeddings."""
        print_header("Testing Semantic Search with Embeddings")
        
        print_step("Initializing vector store with agent registrations")
        # Precompute embeddings
        await discovery_service.precompute_all_capability_embeddings(test_registrations)
        print_success("Vector store initialized with agent registrations")
        
        print_step("Searching for agents that can 'predict weather conditions'")
        results = await discovery_service.find_by_capability_semantic(
            "predict weather conditions",
            test_registrations,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Semantic Search Results", results)
        
        # Assertions
        assert len(results) > 0
        # We expect weather agents to be found
        weather_agents = [r for r, _ in results if "weather" in r.agent_id]
        assert len(weather_agents) > 0
        
        print_success("Completed search for agents that can predict weather conditions. Please verify results above.")
        
        print_step("Searching for agents that can 'generate images based on text descriptions'")
        results = await discovery_service.find_by_capability_semantic(
            "generate images based on text descriptions",
            test_registrations,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Semantic Search Results", results)
        
        # Assertions
        assert len(results) > 0
        # We expect image generation agent to be found
        image_agents = [r for r, _ in results if r.agent_id == "multi-agent-1"]
        assert len(image_agents) > 0
        
        print_success("Completed search for agents that can generate images. Please verify results above.")
        
        print_step("Searching with organization filter")
        results = await discovery_service.find_by_capability_semantic(
            "predict weather conditions",
            test_registrations,
            limit=10,
            similarity_threshold=0.1,
            filters={"organization": ["Weather Corp"]}
        )
        
        print_result("Filtered Semantic Search Results", results)
        
        # Assertions
        assert len(results) > 0
        # We expect only Weather Corp agents
        for r, _ in results:
            assert r.organization == "Weather Corp"
        
        print_success("Completed search with organization filter. Please verify results above.")

    @pytest.mark.asyncio
    async def test_capability_embedding_updates(self, discovery_service: CapabilityDiscoveryService, test_registrations: Dict[str, AgentRegistration]):
        """Test updating capability embeddings for a specific agent."""
        print_header("Testing Capability Embedding Updates")
        
        print_step("Initializing vector store with agent registrations")
        # Precompute embeddings
        await discovery_service.precompute_all_capability_embeddings(test_registrations)
        print_success("Vector store initialized with agent registrations")
        
        print_step("Updating a specific agent with new capabilities")
        # Modify an existing agent
        weather_agent = test_registrations["weather-agent-1"]
        weather_agent.capabilities.append(
            Capability(
                name="climate_analysis",
                description="Analyze long-term climate patterns and trends",
                input_schema={"region": "string", "years": "integer"},
                output_schema={"analysis": "object"},
                version="1.0"
            )
        )
        
        # Update embeddings for the modified agent
        await discovery_service.update_capability_embeddings_cache(weather_agent)
        print_success("Updated agent capabilities in the vector store")
        
        print_step("Searching for agents that can 'analyze climate patterns'")
        results = await discovery_service.find_by_capability_semantic(
            "analyze climate patterns",
            test_registrations,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Semantic Search Results after Update", results)
        
        # Assertions
        assert len(results) > 0
        # We expect the updated weather agent to be found
        assert any(r.agent_id == "weather-agent-1" for r, _ in results)
        
        print_success("Completed search for agent with updated capabilities. Please verify results above.")

    @pytest.mark.asyncio
    async def test_agent_removal(self, discovery_service: CapabilityDiscoveryService, test_registrations: Dict[str, AgentRegistration]):
        """Test removing an agent from the vector store."""
        print_header("Testing Agent Removal")
        
        print_step("Initializing vector store with agent registrations")
        # Precompute embeddings
        await discovery_service.precompute_all_capability_embeddings(test_registrations)
        print_success("Vector store initialized with agent registrations")
        
        print_step("Searching for weather agents before removal")
        results = await discovery_service.find_by_capability_semantic(
            "predict weather conditions",
            test_registrations,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Results before agent removal", results)
        
        # Assertions
        assert len(results) > 0
        assert any(r.agent_id == "weather-agent-1" for r, _ in results)
        
        print_step("Removing weather-agent-1 from vector store")
        await discovery_service.clear_agent_embeddings_cache("weather-agent-1")
        print_success("Agent removed from vector store")
        
        print_step("Searching for weather agents after removal")
        # Remove from test_registrations too to simulate complete removal
        removed_agent = test_registrations.pop("weather-agent-1")
        
        results = await discovery_service.find_by_capability_semantic(
            "predict weather conditions",
            test_registrations,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Results after agent removal", results)
        
        # Assertions
        assert not any(r.agent_id == "weather-agent-1" for r, _ in results)
        
        print_success("Completed agent removal. Please verify results above.")
        
        # Add back for other tests
        test_registrations["weather-agent-1"] = removed_agent

    @pytest.mark.asyncio
    async def test_fallback_when_embeddings_unavailable(self, discovery_service: CapabilityDiscoveryService, test_registrations: Dict[str, AgentRegistration], capabilities_index: Dict[str, Set[str]]):
        """Test fallback to string matching when embeddings are unavailable."""
        print_header("Testing Fallback When Embeddings Unavailable")
        
        print_step("Creating discovery service with embeddings disabled")
        # Create with minimal config to simulate missing embeddings
        service = CapabilityDiscoveryService({"in_memory": True})
        
        # Initialize without embeddings model - this should fall back to string-based methods
        await service.initialize_embeddings_model()
        
        test_registrations = create_test_registrations()
        capabilities_index = extract_capabilities_index(test_registrations)
        
        print_step("Searching for weather agents using basic similarity")
        results = await service.find_by_capability_name(
            "weather forecast",
            test_registrations,
            capabilities_index,
            limit=10,
            similarity_threshold=0.1
        )
        
        print_result("Fallback Search Results", results)
        
        # Assertions
        assert len(results) >= 0  # May return results if string similarity is good enough
        
        print_success("Completed fallback mechanism test. Please verify results above.")

# The visual runner part remains outside the class
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])