"""
Pytest fixtures for capability discovery tests.

This module provides shared fixtures for the capability discovery tests.
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from typing import List

# Import from agentconnect
from agentconnect.core.types import AgentType, AgentIdentity, Capability, InteractionMode, Skill
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.registry.capability_discovery import CapabilityDiscoveryService
from agentconnect.core.registry.capability_discovery_impl.embedding_utils import (
    check_semantic_search_requirements,
    create_huggingface_embeddings
)
from agentconnect.core.registry.capability_discovery_impl.qdrant_client import (
    initialize_qdrant_clients
)

# Sample test data
@pytest.fixture
def test_capabilities():
    """Provide sample capabilities for testing."""
    return [
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

@pytest.fixture
def create_test_registration():
    """Provide a function to create test registrations."""
    def _create(
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
    
    return _create

@pytest.fixture
def test_registrations(test_capabilities, create_test_registration):
    """Provide test agent registrations."""
    registrations = {}
    
    # Weather agent
    weather_agent = create_test_registration(
        agent_id="weather-agent-1",
        name="Weather Forecaster",
        description="Provides detailed weather forecasts for locations around the world",
        capabilities=[test_capabilities[0]],
        organization="Weather Corp",
        developer="Climate Team"
    )
    registrations[weather_agent.agent_id] = weather_agent
    
    # Finance agent
    finance_agent = create_test_registration(
        agent_id="finance-agent-1",
        name="Stock Analyzer",
        description="Provides real-time stock market data and analysis",
        capabilities=[test_capabilities[1]],
        organization="Finance Inc",
        developer="Market Analysis Team"
    )
    registrations[finance_agent.agent_id] = finance_agent
    
    # News agent
    news_agent = create_test_registration(
        agent_id="news-agent-1",
        name="News Aggregator",
        description="Aggregates and searches news from multiple sources",
        capabilities=[test_capabilities[2]],
        organization="News Network",
        developer="Content Team"
    )
    registrations[news_agent.agent_id] = news_agent
    
    # Multi-capability agent
    multi_agent = create_test_registration(
        agent_id="multi-agent-1",
        name="Creative Assistant",
        description="Helps with creative tasks including image generation and code completion",
        capabilities=[test_capabilities[3], test_capabilities[4]],
        organization="Creative Studio",
        developer="AI Team"
    )
    registrations[multi_agent.agent_id] = multi_agent
    
    # Another weather agent from different org
    alt_weather_agent = create_test_registration(
        agent_id="weather-agent-2",
        name="Global Weather Service",
        description="Provides global weather data and forecasts using satellite imagery",
        capabilities=[test_capabilities[0]],
        organization="Global Weather Inc",
        developer="Meteorology Team"
    )
    registrations[alt_weather_agent.agent_id] = alt_weather_agent
    
    return registrations

@pytest.fixture
def capabilities_index(test_registrations):
    """Provide a capability index for testing."""
    capabilities_index = {}
    
    for agent_id, registration in test_registrations.items():
        for capability in registration.capabilities:
            if capability.name not in capabilities_index:
                capabilities_index[capability.name] = set()
            capabilities_index[capability.name].add(agent_id)
    
    return capabilities_index

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Clean up
    shutil.rmtree(temp_dir)

@pytest.fixture
async def embeddings_model():
    """Provide an embeddings model for testing."""
    if not check_semantic_search_requirements()["embedding_model"]:
        pytest.skip("Embedding model not available")
        return None
    
    config = {"model_name": "all-MiniLM-L6-v2"}  # Use small model for tests
    return create_huggingface_embeddings(config)

@pytest.fixture
async def qdrant_clients():
    """Provide Qdrant clients for testing."""
    if not check_semantic_search_requirements()["qdrant"]:
        pytest.skip("Qdrant client not available")
        return None, None
    
    config = {"in_memory": True}
    return await initialize_qdrant_clients(config)

@pytest.fixture
async def discovery_service():
    """Provide a discovery service for testing."""
    # Create with in-memory Qdrant
    service = CapabilityDiscoveryService({
        "in_memory": True,
        "use_quantization": False,  # Disable for faster tests
        "model_name": "all-MiniLM-L6-v2"  # Use small model for faster tests
    })
    
    # Initialize embeddings model
    await service.initialize_embeddings_model()
    
    yield service 