import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from langchain_core.tools.structured import StructuredTool
from pydantic import BaseModel, Field

from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.registry.registration import AgentRegistration, Capability, Skill
from agentconnect.core.types import AgentType

logger = logging.getLogger(__name__)

# --- Updated Input/Output schemas for agent search tool ---


class AgentSearchInput(BaseModel):
    """Input schema for agent search."""

    query: str = Field(
        description="The natural language query describing the desired capability, skill, or agent function. This will be used for semantic search against agent profiles."
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of agent results to return (default 5).",
    )
    strictness: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Similarity threshold (0.0 to 1.0). Results below this score are typically excluded. Higher values mean stricter matching. Default is 0.2.",
    )
    output_detail: str = Field(
        default="summary",
        description="Controls the level of detail in the returned agent information. Options: 'minimal', 'summary', 'capabilities', 'full'. Default is 'summary'.",
        pattern="^(minimal|summary|capabilities|full)$",
    )
    include_tags: Optional[List[str]] = Field(
        default=None,
        description="Optional list of tags. If provided, results will be filtered to agents that have AT LEAST ONE of these exact tags, in addition to semantic query matching.",
    )


class AgentSearchResultItem(BaseModel):
    """Defines the structure for each agent in the search results."""

    # Required fields
    agent_id: str = Field(description="Unique identifier for the agent.")
    similarity_score: float = Field(
        description="Relevance score of the agent to the main query (e.g., 0.0 to 1.0+). Higher is generally better."
    )

    # Minimal level fields
    name: Optional[str] = Field(None, description="Name of the agent.")
    url: Optional[str] = Field(
        None,
        description="Endpoint URL for the agent, if applicable for direct or future A2A communication.",
    )
    payment_address: Optional[str] = Field(
        None,
        description="Agent's primary wallet address if payments are required for its services.",
    )

    # Summary level fields
    summary: Optional[str] = Field(
        None, description="Brief summary of the agent's purpose and functions."
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Keywords associated with the agent for categorization or filtering.",
    )

    # Capabilities level fields
    capabilities: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of capabilities (each a dict with 'name' and 'description') the agent provides.",
    )
    skills: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of skills (each a dict with 'name' and 'description') the agent possesses.",
    )

    # Full level fields
    description: Optional[str] = Field(
        None,
        description="Detailed description of the agent, its functionalities, and use cases.",
    )
    examples: Optional[List[str]] = Field(
        None,
        description="Example inputs, outputs, or interaction scenarios for the agent.",
    )
    version: Optional[str] = Field(
        None, description="Version of the agent software or definition."
    )
    organization: Optional[str] = Field(
        None,
        description="The organization or entity providing or responsible for the agent.",
    )
    developer: Optional[str] = Field(
        None, description="The individual or team that developed the agent."
    )
    auth_schemes: Optional[List[str]] = Field(
        None,
        description="List of authentication schemes supported or required by the agent (for future use or specific integrations).",
    )
    default_input_modes: Optional[List[str]] = Field(
        None,
        description="List of primary data types or modes the agent accepts as input (e.g., 'text', 'application/json').",
    )
    default_output_modes: Optional[List[str]] = Field(
        None,
        description="List of primary data types or modes the agent produces as output.",
    )

    class Config:
        """Config for the AgentSearchResultItem."""

        extra = "ignore"


class AgentSearchOutput(BaseModel):
    """Output schema for agent search, containing a list of results."""

    message: str = Field(
        description="A summary message about the search operation (e.g., 'Successfully found X agents', 'No agents matched your criteria', or error details)."
    )
    results: List[AgentSearchResultItem] = Field(
        default_factory=list,
        description="A list of found agents. Each item's detail level is determined by the 'output_detail' input parameter.",
    )

    def __str__(self) -> str:
        """Return a clean JSON string representation."""
        return self.model_dump_json(indent=2, exclude_none=True)


# --- Implementation of agent search tool ---


def _format_capabilities_for_output(cap_list: List[Capability]) -> List[Dict[str, str]]:
    return [
        {"name": cap.name, "description": cap.description or ""} for cap in cap_list
    ]


def _format_skills_for_output(skill_list: List[Skill]) -> List[Dict[str, str]]:
    return [
        {"name": skill.name, "description": skill.description or ""}
        for skill in skill_list
    ]


def _populate_search_result_item(
    registration: AgentRegistration, similarity_score: float, output_detail_level: str
) -> AgentSearchResultItem:
    """Helper to populate AgentSearchResultItem based on output_detail_level."""
    item_data = {
        "agent_id": registration.agent_id,
        "similarity_score": round(similarity_score, 4),
    }

    # Minimal level fields (always try to populate if available)
    if registration.name:
        item_data["name"] = registration.name
    if registration.url:
        item_data["url"] = registration.url
    if registration.payment_address:
        item_data["payment_address"] = registration.payment_address

    if output_detail_level == "minimal":
        return AgentSearchResultItem(**item_data)

    # Summary level fields
    if registration.summary:
        item_data["summary"] = registration.summary
    if registration.tags:
        item_data["tags"] = registration.tags

    if output_detail_level == "summary":
        return AgentSearchResultItem(**item_data)

    # Capabilities level fields
    if registration.capabilities:
        item_data["capabilities"] = _format_capabilities_for_output(
            registration.capabilities
        )
    if (
        registration.skills
    ):  # Assuming skills structure is similar or defined in AgentRegistration
        item_data["skills"] = _format_skills_for_output(registration.skills)

    if output_detail_level == "capabilities":
        return AgentSearchResultItem(**item_data)

    # Full level fields (all remaining defined in AgentSearchResultItem)
    if registration.description:
        item_data["description"] = registration.description
    if registration.examples:
        item_data["examples"] = registration.examples
    if registration.version:
        item_data["version"] = registration.version
    if registration.organization:
        item_data["organization"] = registration.organization
    if registration.developer:
        item_data["developer"] = registration.developer
    if registration.auth_schemes:
        item_data["auth_schemes"] = registration.auth_schemes
    if registration.default_input_modes:
        item_data["default_input_modes"] = registration.default_input_modes
    if registration.default_output_modes:
        item_data["default_output_modes"] = registration.default_output_modes

    return AgentSearchResultItem(**item_data)


def create_agent_search_tool(
    agent_registry: Optional[AgentRegistry] = None,
    current_agent_id: Optional[str] = None,
    communication_hub: Optional[CommunicationHub] = None,
) -> StructuredTool:
    """
    Create a tool for searching agents by capability, with fine-grained output and tag filtering.

    Args:
        agent_registry: Registry for accessing agent information
        current_agent_id: ID of the agent currently using the tool
        communication_hub: Hub for agent communication

    Returns:
        A StructuredTool for agent search that can be used in agent workflows
    """
    standalone_mode = agent_registry is None  # Simplified standalone check

    base_description = (
        "Finds other agents by semantically searching their profiles (name, description, capabilities, skills, tags, examples). "
        "You can specify the desired level of detail for results and filter by exact tags."
    )

    # Standalone mode implementation (returns empty results with explanation)
    if standalone_mode:

        def search_agents_standalone(
            query: str,
            top_k: int = 5,
            strictness: float = 0.2,
            output_detail: str = "summary",
            include_tags: Optional[List[str]] = None,
        ) -> AgentSearchOutput:
            """Standalone implementation that explains limitations."""
            logger.warning(f"Agent search called in standalone mode for query: {query}")
            return AgentSearchOutput(
                message=(
                    f"Agent search for query '{query}' is not available in standalone mode. "
                    "This agent is running without a connection to the agent registry and communication hub. "
                    "Internal capabilities should be used, or connection to a multi-agent system enabled."
                ),
                results=[],
            )

        description = f"[STANDALONE MODE] {base_description} Note: In standalone mode, this tool explains why search isn't available and returns no agents."
        tool_function = search_agents_standalone
        is_async = False
    else:
        # Connected mode implementation
        async def search_agents_async_impl(
            query: str,
            top_k: int = 5,
            strictness: float = 0.2,
            output_detail: str = "summary",
            include_tags: Optional[List[str]] = None,
        ) -> AgentSearchOutput:
            """
            Asynchronously search for agents based on a query and optional filters.

            This is the core asynchronous implementation for agent search in connected mode.
            It queries the agent registry, applies exclusions, and formats results
            based on the requested output detail level.

            Args:
                query: The natural language query describing the desired capability or agent function.
                top_k: Maximum number of agent results to return.
                strictness: Similarity threshold for matching.
                output_detail: Controls the level of detail in the returned agent information.
                include_tags: Optional list of exact tags to filter results by.

            Returns:
                AgentSearchOutput containing the search results and a message.
            """
            logger.debug(
                f"Searching agents: query='{query}', top_k={top_k}, strictness={strictness}, "
                f"output_detail='{output_detail}', include_tags={include_tags}"
            )

            agents_to_exclude: List[str] = []
            if current_agent_id:
                agents_to_exclude.append(current_agent_id)
                if (
                    communication_hub
                ):  # communication_hub might be None even if agent_registry is present
                    try:
                        agent = await communication_hub.get_agent(current_agent_id)
                        if agent:
                            if hasattr(agent, "active_conversations"):
                                agents_to_exclude.extend(
                                    list(agent.active_conversations.keys())
                                )
                            if hasattr(agent, "pending_requests"):
                                agents_to_exclude.extend(
                                    list(agent.pending_requests.keys())
                                )
                            # Simplified recent message exclusion for brevity; could be expanded
                    except Exception as e:
                        logger.warning(
                            f"Could not get active/pending conversations for exclusion: {e}"
                        )

            agents_to_exclude = list(set(agents_to_exclude))
            logger.debug(
                f"Excluding {len(agents_to_exclude)} agent IDs: {agents_to_exclude}"
            )

            # Prepare filters for the registry search
            registry_filters: Optional[Dict[str, List[str]]] = None
            if include_tags:
                registry_filters = {"tags": include_tags}

            try:
                # Use get_by_capability_semantic, which handles qdrant search and fallback
                # The registry's get_by_capability_semantic should accept a filters dict.
                # We assume it passes this to search_with_qdrant.
                found_agents_with_scores: List[Tuple[AgentRegistration, float]] = (
                    await agent_registry.get_by_capability_semantic(
                        capability_description=query,
                        limit=top_k
                        * 2,  # Fetch more to account for exclusions and filtering
                        similarity_threshold=strictness,
                        filters=registry_filters,
                    )
                )

                logger.debug(
                    f"Registry returned {len(found_agents_with_scores)} agents before filtering exclusions."
                )

                processed_results: List[AgentSearchResultItem] = []
                for reg, score in found_agents_with_scores:
                    if (
                        reg.agent_id in agents_to_exclude
                        or reg.agent_type == AgentType.HUMAN
                    ):
                        continue

                    item = _populate_search_result_item(reg, score, output_detail)
                    processed_results.append(item)
                    if len(processed_results) >= top_k:
                        break

                logger.debug(f"Formatted {len(processed_results)} agents for output.")

                if not processed_results:
                    return AgentSearchOutput(
                        message=f"No agents found matching your query '{query}' with specified criteria (tags: {include_tags}).",
                        results=[],
                    )

                return AgentSearchOutput(
                    message=f"Successfully found {len(processed_results)} agents matching your criteria.",
                    results=processed_results,
                )

            except Exception as e:
                logger.exception(f"Error during agent search: {e}")
                return AgentSearchOutput(
                    message=f"Error searching for agents: {str(e)}", results=[]
                )

        # Synchronous wrapper for connected mode
        def search_agents_sync_impl(
            query: str,
            top_k: int = 5,
            strictness: float = 0.2,
            output_detail: str = "summary",
            include_tags: Optional[List[str]] = None,
        ) -> AgentSearchOutput:
            """
            Synchronous wrapper for agent search.

            Args:
                query: The natural language query describing the desired capability or agent function
                top_k: Maximum number of agents to return
                strictness: Minimum similarity score required for results

            Returns:
                AgentSearchOutput with the search results
            """
            try:
                if asyncio.get_event_loop().is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        search_agents_async_impl(
                            query, top_k, strictness, output_detail, include_tags
                        ),
                        asyncio.get_event_loop(),
                    )
                    return future.result()
                else:
                    return asyncio.run(
                        search_agents_async_impl(
                            query, top_k, strictness, output_detail, include_tags
                        )
                    )
            except Exception as e:  # Catch errors from async run or threadsafe future
                logger.error(f"Error in search_agents_sync_impl: {str(e)}")
                return AgentSearchOutput(
                    message=f"Error in search_agents sync wrapper: {str(e)}", results=[]
                )

        description = (
            f"{base_description} "
            "Clearly describe the capabilities you need. Review results carefully. "
            "Similarity scores indicate relevance to your query. "
            "Use 'output_detail' to control how much info is returned for each agent ('minimal', 'summary', 'capabilities', 'full'). "
            "Use 'include_tags' for exact tag matching to refine results."
        )
        tool_function = search_agents_sync_impl
        is_async = True  # The underlying implementation is async

    # Create and return the tool
    # The func should be the synchronous wrapper, and coroutine the async one if is_async is True.
    # If is_async is False (standalone), then coroutine should not be set.
    return StructuredTool.from_function(
        func=tool_function,
        name="search_for_agents",
        description=description,
        args_schema=AgentSearchInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=search_agents_async_impl if is_async else None,
        metadata={"category": "collaboration"},
    )


# Example of how this tool might be registered (illustration purposes)
# if __name__ == '__main__':
#     # This is just for testing the schema and basic flow, does not run full system
#     from agentconnect.core.registry.registration import Capability
#
#     # Mock agent registry for local testing
#     class MockAgentRegistry:
#         async def get_by_capability_semantic(self, capability_description, limit, similarity_threshold, filters=None):
#             print(f"Mock search: {capability_description}, limit {limit}, threshold {similarity_threshold}, filters {filters}")
#             reg1 = AgentRegistration(agent_id="agent1", agent_type=AgentType.AI, name="FinanceBot", summary="Good with numbers",
#                                      capabilities=[Capability(name="calc", description="calculates things")], tags=["finance", "math"],
#                                      payment_address="0x123", url="http://agent1.example.com")
#             reg2 = AgentRegistration(agent_id="agent2", agent_type=AgentType.AI, name="WriterBot", summary="Writes text",
#                                      capabilities=[Capability(name="write", description="writes text")], tags=["writing", "nlp"],
#                                      description="A very detailed description.", examples=["example use case"])
#
#             all_results = [(reg1, 0.9), (reg2, 0.85)]
#
#             # Basic filter sim for testing 'include_tags'
#             if filters and "tags" in filters:
#                 filtered_results = []
#                 required_tags = set(filters["tags"])
#                 for r, s in all_results:
#                     if r.tags and not required_tags.isdisjoint(r.tags):
#                         filtered_results.append((r,s))
#                 return filtered_results
#             return all_results
#
#     # Test function
#     async def test_tool():
#         mock_registry = MockAgentRegistry()
#         search_tool = create_agent_search_tool(agent_registry=mock_registry, current_agent_id="test_caller")
#
#         print("---- Test 1: Default (summary) ----")
#         result1 = await search_tool.acoroutine(query="find someone good with numbers", top_k=1, strictness=0.1)
#         print(result1)
#
#         print("\n---- Test 2: Minimal ----")
#         result2 = await search_tool.acoroutine(query="writers", top_k=1, output_detail="minimal")
#         print(result2)
#
#         print("\n---- Test 3: Full with tag filter----")
#         result3 = await search_tool.acoroutine(query="finance", top_k=1, output_detail="full", include_tags=["finance"])
#         print(result3)
#
#         print("\n---- Test 4: Tag filter no match ----")
#         result4 = await search_tool.acoroutine(query="finance", top_k=1, output_detail="summary", include_tags=["nonexistent_tag"])
#         print(result4)
#
#     if __name__ == '__main__':
#         asyncio.run(test_tool())
