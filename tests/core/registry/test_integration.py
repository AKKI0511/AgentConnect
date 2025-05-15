"""
Integration tests for the CapabilityDiscoveryService.

These tests verify that the CapabilityDiscoveryService correctly integrates
with the AgentRegistry for real-world discovery scenarios.
"""

import asyncio
import pytest
import pytest_asyncio

from agentconnect.core.registry import AgentRegistry
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.types import (
    AgentIdentity,
    AgentType,
    Capability,
    InteractionMode,
    Skill,
)


@pytest_asyncio.fixture(scope="class")
async def registry_instance():
    """Provides a new AgentRegistry instance configured for in-memory Qdrant."""
    # Explicitly configure for in-memory mode for CI/testing
    config = {
        "vector_search_config": {"in_memory": True}
    }
    registry = AgentRegistry(**config) # Pass config here
    await registry.ensure_initialized() # Wait for the background task to finish basic init
    yield registry
    # No explicit teardown needed


@pytest_asyncio.fixture(scope="class", autouse=True)
async def setup_registry_data(registry_instance: AgentRegistry):
    """Registers test agents with the initialized registry instance."""
    # registry_instance is already initialized due to the ensure_initialized call in its fixture
    
    # Create agent identities
    identity1 = AgentIdentity.create_key_based()
    identity2 = AgentIdentity.create_key_based()
    identity3 = AgentIdentity.create_key_based()

    # Register agents (register method implicitly waits via ensure_initialized, but registry itself is ready)
    await registry_instance.register(AgentRegistration(
        agent_id="data-agent",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        identity=identity1,
        name="Data Analyzer",
        summary="Specialized in data analysis and visualization",
        description="This agent can analyze complex datasets, identify patterns, and create visualizations.",
        version="1.0",
        organization="DataCorp",
        developer="DataTeam",
        capabilities=[
            Capability(
                name="analyze_data",
                description="Analyze data and generate insights",
                input_schema={"data": "string"},
                output_schema={"analysis": "string"},
            ),
            Capability(
                name="create_visualization",
                description="Create data visualizations",
                input_schema={"data": "string", "chart_type": "string"},
                output_schema={"visualization": "string"},
            ),
        ],
        skills=[
            Skill(name="statistics", description="Statistical analysis"),
            Skill(name="data_cleaning", description="Data preprocessing and cleaning"),
        ],
        tags=["data", "analysis", "visualization"],
        examples=[
            "Analyze this sales dataset and identify trends",
            "Create a bar chart visualization of monthly revenue",
        ],
    ))

    # Register NLP agent
    await registry_instance.register(AgentRegistration(
        agent_id="nlp-agent",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT, InteractionMode.HUMAN_TO_AGENT],
        identity=identity2,
        name="Language Processor",
        summary="Expert in natural language processing",
        description="This agent specializes in text analysis, sentiment analysis, and language generation.",
        version="2.1",
        organization="NLPTech",
        developer="LangTeam",
        capabilities=[
            Capability(
                name="sentiment_analysis",
                description="Analyze sentiment in text",
                input_schema={"text": "string"},
                output_schema={"sentiment": "string", "score": "number"},
            ),
            Capability(
                name="summarize_text",
                description="Create concise summaries of text",
                input_schema={"text": "string", "max_length": "number"},
                output_schema={"summary": "string"},
            ),
        ],
        skills=[
            Skill(name="text_classification", description="Classify text into categories"),
            Skill(name="entity_extraction", description="Extract named entities from text"),
            Skill(name="language_generation", description="Generate natural language text"),
        ],
        tags=["nlp", "text", "language", "ai"],
        examples=[
            "Analyze the sentiment of this customer review",
            "Summarize this news article in 3 sentences",
        ],
    ))

    # Register general assistant agent
    await registry_instance.register(AgentRegistration(
        agent_id="assistant-agent",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        identity=identity3,
        name="General Assistant",
        summary="Multi-purpose assistant",
        description="A general purpose assistant that can help with various tasks.",
        version="1.0",
        organization="AssistantCorp",
        developer="AssistantTeam",
        capabilities=[
            Capability(
                name="answer_questions",
                description="Answer general knowledge questions",
                input_schema={"question": "string"},
                output_schema={"answer": "string"},
            ),
            Capability(
                name="search_web",
                description="Search the web for information",
                input_schema={"query": "string"},
                output_schema={"results": "array"},
            ),
        ],
        skills=[
            Skill(name="research", description="Research skills for finding information"),
            Skill(name="summarization", description="Summarize information concisely"),
        ],
        tags=["assistant", "general", "search"],
        custom_metadata={
            "expertise_level": "beginner",
            "preferred_language": "English",
        },
        examples=[
            "What is the capital of France?",
            "Search for the latest news about AI",
        ],
    ))
    # No need to wait for _vector_store_initialized event here anymore
    # The individual register calls awaited the embedding updates.


class TestCapabilityDiscoveryIntegration:
    """Integration tests for CapabilityDiscoveryService with AgentRegistry."""

    @pytest.mark.asyncio
    async def test_registry_integration(self, registry_instance: AgentRegistry):
        """Test that registry integration works correctly."""
        # Check that all agents are registered
        registrations = await registry_instance.get_all_agents()
        assert len(registrations) == 3
        
    @pytest.mark.asyncio
    async def test_find_by_capability(self, registry_instance: AgentRegistry):
        """Test finding agents by capability within the registry."""
        # Search for data analysis capabilities
        results = await registry_instance.get_by_capability_semantic(
            "Analyze sales data and create charts",
            limit=2,
        )
        
        # Check results
        assert len(results) > 0
        first_agent, score = results[0]
        assert first_agent.agent_id == "data-agent"
        assert score > 0.3
        
    @pytest.mark.asyncio
    async def test_capability_update(self, registry_instance: AgentRegistry):
        """Test updating agent capabilities."""
        # Define the updates for the NLP agent
        agent_id_to_update = "nlp-agent"
        updates = {
            "name": "Language Processor Pro",
            "summary": "Advanced language processing capabilities",
            "description": "Enhanced language processing with translation capabilities",
            "capabilities": [
                Capability(
                    name="sentiment_analysis", # Keep one old capability
                    description="Analyze sentiment in text",
                    input_schema={"text": "string"}, # Ensure schema is present
                    output_schema={"sentiment": "string", "score": "number"},
                ),
                Capability(
                    name="translate_text", # Add new capability
                    description="Translate text between languages",
                    input_schema={"text": "string", "source_lang": "string", "target_lang": "string"},
                    output_schema={"translation": "string"},
                ),
            ],
            "tags": ["nlp", "text", "language", "translation"], # Update tags as well
            # No need to provide identity for update
        }
        
        # Update the agent using update_registration
        updated_agent = await registry_instance.update_registration(agent_id_to_update, updates)
        assert updated_agent is not None, f"Agent {agent_id_to_update} should exist for update."
        
        # Allow some time for the background embedding update task to process
        await asyncio.sleep(0.2)
        
        # Search for translation capabilities to verify the update
        results = await registry_instance.get_by_capability_semantic(
            "translate text from English to Spanish",
        )
        
        # Verify the results
        assert len(results) > 0
        found_nlp_agent = False
        for agent, score in results:
            if agent.agent_id == agent_id_to_update:
                assert agent.name == "Language Processor Pro", "Agent name was not updated correctly."
                # Check if the new capability is part of its capabilities
                assert any(cap.name == "translate_text" for cap in agent.capabilities), "New capability 'translate_text' not found."
                # Check if old capability 'summarize_text' was removed (as it wasn't in the update)
                assert not any(cap.name == "summarize_text" for cap in agent.capabilities), "Old capability 'summarize_text' should have been removed."
                # Check tags
                assert agent.tags == updates["tags"], "Tags were not updated correctly."
                found_nlp_agent = True
                break
        assert found_nlp_agent, f"Updated agent {agent_id_to_update} not found in search results for new capability."
        
    @pytest.mark.asyncio
    async def test_organization_filtering(self, registry_instance: AgentRegistry):
        """Test filtering by organization."""
        results = await registry_instance.get_by_capability_semantic(
            "analyze", # Broad term, relies on semantic search
            filters={"organization": ["DataCorp"]},
        )
        
        # Verify the results
        assert len(results) == 1
        first_agent, _ = results[0]
        assert first_agent.agent_id == "data-agent"
        
    @pytest.mark.asyncio
    async def test_metadata_integration(self, registry_instance: AgentRegistry):
        """Test integration with custom metadata."""
        custom_reg = await registry_instance.get_registration("assistant-agent")
        assert custom_reg is not None
        assert custom_reg.custom_metadata.get("expertise_level") == "beginner"
        assert custom_reg.custom_metadata.get("preferred_language") == "English"
        
    @pytest.mark.asyncio
    async def test_agent_removal(self, registry_instance: AgentRegistry):
        """Test removing an agent from the registry and discovery service."""
        # Remove the data agent
        await registry_instance.unregister("data-agent")
        
        # Verify it's removed
        all_regs = await registry_instance.get_all_agents()
        # There were 3 agents, one is removed.
        assert len(all_regs) == 2 
        
        # Search for data analysis - should not find the removed agent
        results = await registry_instance.get_by_capability_semantic(
            "data analysis and visualization",
        )
        
        # Either we get no results, or the data agent is not in the results
        if results:
            for agent, _ in results:
                assert agent.agent_id != "data-agent"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])