import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools.structured import StructuredTool

from agentconnect.index.registry import AgentRegistry, AgentRegistration
from agentconnect.core.types import AgentType

# Import from centralized schemas and utilities
from agentconnect.index.registry.search import (
    AgentSearchInput,
    AgentSearchOutput,
    AgentSearchResultItem,
    populate_search_result_item,
)

logger = logging.getLogger(__name__)

# --- Implementation of agent search tool ---


def create_agent_search_tool(
    agent_registry: Optional[AgentRegistry] = None,
    current_agent_id: Optional[str] = None,
    communication_hub: Optional[Any] = None,
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
                    except Exception:
                        pass

            agents_to_exclude = list(set(agents_to_exclude))

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

                processed_results: List[AgentSearchResultItem] = []
                for reg, score in found_agents_with_scores:
                    if (
                        reg.agent_id in agents_to_exclude
                        or reg.agent_type == AgentType.HUMAN
                    ):
                        continue

                    # Use the centralized utility function
                    item = populate_search_result_item(reg, score, output_detail)
                    processed_results.append(item)
                    if len(processed_results) >= top_k:
                        break

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
                logger.exception("Error during agent search: %s", e)
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
                logger.error("Error in search_agents_sync_impl: %s", str(e))
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
