"""
MCP server for agent registry search operations.

This server provides semantic search capabilities for the AgentConnect registry,
allowing clients to find agents based on their capabilities, skills, and descriptions.
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import httpx

from mcp.server.fastmcp import FastMCP, Context

from agentconnect.clients.registry_client import RegistryAPIClient
from agentconnect.core.registry.search import (
    populate_search_result_item,
)
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.types import AgentType
from agentconnect.config import settings as agentconnect_settings

# --- Logging Setup ---
logger = logging.getLogger(__name__)


# --- Health Constants ---
HEALTH_TIMEOUT_SECONDS = 5.0


# --- Application Context ---
@dataclass
class AppContext:
    """Application context containing shared resources."""

    registry_client: RegistryAPIClient
    is_healthy: bool = False


# --- Health Check ---
async def check_registry_api_health() -> bool:
    """Check if the Registry API server is running and healthy."""
    try:
        # Use the client settings to get the base URL for health checks
        base_url = agentconnect_settings.clients.registry.base_url
        if not base_url:
            raise RuntimeError("clients.registry.base_url is not configured")
        if not base_url.endswith("/"):
            base_url += "/"

        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{base_url}health")
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Registry API health check: {health_data}")
                return health_data.get("status") == "healthy"
    except Exception as e:
        logger.warning(f"Registry API health check failed: {e}")
        return False
    return False


# --- Lifespan Management ---
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with shared registry client."""
    logger.info("Starting AgentConnect agent discovery MCP tools...")
    defaults = agentconnect_settings.mcp.agent_discovery
    logger.info(
        "Agent discovery defaults: top_k=%s, strictness=%s, output_detail=%s",
        defaults.top_k,
        defaults.strictness,
        defaults.output_detail,
    )

    # Initialize registry client
    registry_client = RegistryAPIClient()

    # Check health on startup
    is_healthy = await check_registry_api_health()
    if is_healthy:
        logger.info("Registry API is healthy and ready")
    else:
        logger.warning("Registry API is not healthy - search operations may fail")

    context = AppContext(registry_client=registry_client, is_healthy=is_healthy)

    try:
        yield context
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down AgentConnect agent discovery MCP tools...")
        await context.registry_client.close()


# --- MCP Server Instance ---
mcp = FastMCP(
    name="agentconnect-registry",
    lifespan=app_lifespan,
    instructions="""You can discover agents in the collaborative network to work with. Search by the capabilities you need, then use their agent_id to send collaboration requests. Think of this as your agent directory for finding the right partners for any task.

Common patterns:
- Task Delegation: Find agents who can handle specific tasks you can't do
- Capability Expansion: Discover agents with complementary skills  
- Load Balancing: Find multiple agents for the same task to distribute workload
- Backup Planning: Identify alternatives in case your first choice is unavailable

Each result includes an agent_id - save this to send collaboration requests to that agent.""",
)


# --- Enhanced Search Tool with Pydantic Models ---
@mcp.tool(
    name="search_for_agents",
    title="Discover Collaboration Partners",
)
async def search_for_agents_tool(
    ctx: Context,
    query: str,
    top_k: int = agentconnect_settings.mcp.agent_discovery.top_k,
    strictness: float = agentconnect_settings.mcp.agent_discovery.strictness,
    output_detail: str = agentconnect_settings.mcp.agent_discovery.output_detail,
    include_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Discover agents in the network to collaborate with. Search by the capabilities you need, then use their agent_id to send collaboration requests.

    Args:
        query: Describe what you need help with or want to delegate (e.g., 'telegram broadcasting', 'PDF processing', 'image generation')
        top_k: Number of collaborators to discover (1-20). Use 2-3 for simple tasks, 5-10 for options/backups
        strictness: Match precision: 0.2 for broad discovery, 0.5 for good matches, 0.8+ for precise requirements
        output_detail: 'minimal' for browsing, 'summary' for basic vetting, 'capabilities' for evaluation, 'full' for detailed assessment
        include_tags: Filter by specialization (optional). Use when you know the exact domain (e.g., ['telegram', 'social media'])

    Returns:
        Dictionary with search results and status message. Each result includes an agent_id for collaboration requests.
        Returns empty results with helpful message if no agents match your criteria.
    """
    # Validate output_detail
    valid_output_details = ["minimal", "summary", "capabilities", "full"]
    if output_detail not in valid_output_details:
        error_msg = f"Invalid output_detail level '{output_detail}'. Must be one of {valid_output_details}"
        await ctx.error(error_msg)
        return {"message": error_msg, "results": []}

    # Get the shared application context
    app_ctx: AppContext = ctx.request_context.lifespan_context

    await ctx.debug(
        f"MCP Tool 'search_for_agents' called with query: '{query}', "
        f"top_k: {top_k}, strictness: {strictness}, "
        f"output_detail: '{output_detail}', include_tags: {include_tags}"
    )

    # Check if Registry API is available
    if not app_ctx.is_healthy:
        # Re-check health in case it recovered
        app_ctx.is_healthy = await check_registry_api_health()

        if not app_ctx.is_healthy:
            expected = agentconnect_settings.clients.registry.base_url or "<unset>"
            if not expected.endswith("/"):
                expected += "/"
            error_msg = (
                f"Agent search for query '{query}' is not available. "
                "Registry API server is not running or healthy. "
                f"Expected location: {expected}health. "
                "Please ensure the AgentConnect Registry API server is running."
            )
            await ctx.error(error_msg)
            return {"message": error_msg, "results": []}

    try:
        # Prepare filters for the registry search
        registry_filters: Optional[Dict[str, List[str]]] = None
        if include_tags:
            registry_filters = {"tags": include_tags}

        # Use the shared registry client from lifespan context
        found_agents_with_scores: List[Tuple[AgentRegistration, float]] = (
            await app_ctx.registry_client.get_by_capability_semantic(
                capability_description=query,
                limit=top_k * 2,  # Fetch more to account for exclusions and filtering
                similarity_threshold=strictness,
                filters=registry_filters,
            )
        )

        await ctx.debug(
            f"Registry returned {len(found_agents_with_scores)} agents before filtering."
        )

        processed_results: List[Dict[str, Any]] = []
        for reg, score in found_agents_with_scores:
            # Filter out HUMAN agents
            if reg.agent_type == AgentType.HUMAN:
                continue

            # Use the registry search utility function to get Pydantic model
            item = populate_search_result_item(reg, score, output_detail)
            processed_results.append(item.model_dump(exclude_none=True))
            if len(processed_results) >= top_k:
                break

        await ctx.debug(f"Formatted {len(processed_results)} agents for output.")

        if not processed_results:
            filter_text = f" with tags {include_tags}" if include_tags else ""
            suggestions = []
            if strictness > 0.6:
                suggestions.append(
                    "try lowering strictness to 0.5 or 0.2 for broader discovery"
                )
            if include_tags:
                suggestions.append("try removing tag filters to expand search")
            if not suggestions:
                suggestions.append(
                    "try different keywords or lower strictness (0.2-0.5)"
                )

            suggestion_text = f" Try: {', '.join(suggestions)}." if suggestions else ""
            return {
                "message": f"No agents found matching '{query}'{filter_text} (similarity >= {strictness}).{suggestion_text}",
                "results": [],
            }

        return {
            "message": f"Successfully found {len(processed_results)} agents matching your criteria.",
            "results": processed_results,
        }

    except Exception as e:
        await ctx.error(f"Error during agent search: {e}")
        return {"message": f"Error searching for agents: {str(e)}", "results": []}


# --- Main Entry Point ---
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Early exit if disabled
        if not agentconnect_settings.mcp.agent_discovery.enabled:
            logger.info(
                "Agent discovery is disabled via settings.mcp.agent_discovery.enabled=false. Exiting."
            )
            sys.exit(0)

        # Run with stdio transport for MCP clients like Cursor
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}", exc_info=True)
        sys.exit(1)
