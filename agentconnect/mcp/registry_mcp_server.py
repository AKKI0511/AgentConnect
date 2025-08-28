"""
MCP server for agent registry search operations.

This server provides semantic search capabilities for the AgentConnect registry,
allowing clients to find agents based on their capabilities, skills, and descriptions.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from mcp.server.fastmcp import FastMCP, Context

from agentconnect.clients.registry_client import RegistryAPIClient
from agentconnect.core.registry.search import (
    populate_search_result_item,
)
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.types import AgentType


# --- Private helpers (no settings access at import time) ---
_HEALTH_TIMEOUT_SECONDS = 5.0


async def _check_registry_api_health(base_url: str, timeout_seconds: float) -> bool:
    """Pure helper: check if the Registry API server is healthy.

    This function performs an HTTP GET to the provided base_url/health and
    returns True if status is 'healthy'.
    """
    try:
        url = base_url if base_url.endswith("/") else f"{base_url}/"
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{url}health")
            if response.status_code == 200:
                health_data = response.json()
                return health_data.get("status") == "healthy"
    except Exception:
        return False
    return False


# --- Pure business-logic helpers for testability ---
def _validate_output_detail_level(output_detail: str) -> Optional[str]:
    """Return error message if invalid output detail level, otherwise None."""
    valid_output_details = ["minimal", "summary", "capabilities", "full"]
    if output_detail not in valid_output_details:
        return f"Invalid output_detail level '{output_detail}'. Must be one of {valid_output_details}"
    return None


def _prepare_registry_filters(
    include_tags: Optional[List[str]],
) -> Optional[Dict[str, List[str]]]:
    """Build registry filters payload from optional tag list."""
    if include_tags:
        return {"tags": include_tags}
    return None


def _build_suggestions(strictness: float, include_tags: Optional[List[str]]) -> str:
    """Suggest search adjustments for empty result cases."""
    suggestions: List[str] = []
    if strictness > 0.6:
        suggestions.append(
            "try lowering strictness to 0.5 or 0.2 for broader discovery"
        )
    if include_tags:
        suggestions.append("try removing tag filters to expand search")
    if not suggestions:
        suggestions.append("try different keywords or lower strictness (0.2-0.5)")
    return f" {', '.join(suggestions)}."


def _filter_and_format_results(
    found_agents_with_scores: List[Tuple[AgentRegistration, float]],
    output_detail: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    """Filter out HUMAN agents and format results up to top_k using the registry utility."""
    processed_results: List[Dict[str, Any]] = []
    for reg, score in found_agents_with_scores:
        if reg.agent_type == AgentType.HUMAN:
            continue
        item = populate_search_result_item(reg, score, output_detail)
        processed_results.append(item.model_dump(exclude_none=True))
        if len(processed_results) >= top_k:
            break
    return processed_results


def _build_registry_unavailable_message(query: str) -> str:
    """Generic user-facing message when registry is unavailable (no internal details)."""
    return (
        f"Agent search for query '{query}' is not available. "
        "Registry API server is not running or healthy. "
        "Please ensure the AgentConnect Registry API server is running."
    )


# --- MCP Factory (owns tools and lifespan) ---
def create_agent_discovery_mcp(
    registry_client: Optional[RegistryAPIClient] = None,
) -> FastMCP:
    """Create and return a configured FastMCP instance for agent discovery.

    - Tools and lifespan are defined inside this factory and close over a
      snapshot of settings read at call-time.
    - Allows dependency injection for tests (registry_client).
    - No network calls or client creation occur at import time.
    """

    # Read settings snapshot at factory call-time only
    from agentconnect.config import settings as agentconnect_settings  # local import

    discovery_cfg = agentconnect_settings.mcp.agent_discovery
    client_cfg = agentconnect_settings.clients.registry

    default_top_k = discovery_cfg.top_k
    default_strictness = discovery_cfg.strictness
    default_output_detail = discovery_cfg.output_detail
    base_url = client_cfg.base_url

    # Application context is local to the factory
    @dataclass
    class AppContext:
        """Application context containing shared resources."""

        registry_client: RegistryAPIClient
        is_healthy: bool = False

    # Lifespan defined within factory to capture snapshot and DI
    @asynccontextmanager
    async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
        """Manage application lifecycle with shared registry client."""
        # Use provided client or create a new one lazily
        client = registry_client or RegistryAPIClient()

        # Health check on startup using provided/derived base_url
        is_healthy = await _check_registry_api_health(base_url, _HEALTH_TIMEOUT_SECONDS)

        context = AppContext(registry_client=client, is_healthy=is_healthy)
        try:
            yield context
        finally:
            await context.registry_client.close()

    # Tool implementation defined within factory; no settings defaults in signature
    async def search_for_agents_tool(
        ctx: Context,
        query: str,
        top_k: int = default_top_k,
        strictness: float = default_strictness,
        output_detail: str = default_output_detail,
        include_tags: List[str] = None,
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
        error_msg = _validate_output_detail_level(output_detail)
        if error_msg:
            await ctx.error(error_msg)
            return {"message": error_msg, "results": []}

        # Get the shared application context
        app_ctx: AppContext = ctx.request_context.lifespan_context

        await ctx.debug(
            f"search_for_agents: query='{query}', top_k={top_k}, strictness={strictness}, "
            f"output_detail='{output_detail}', include_tags={include_tags}"
        )

        # Check if Registry API is available
        if not app_ctx.is_healthy:
            # Re-check health in case it recovered
            app_ctx.is_healthy = await _check_registry_api_health(
                base_url, _HEALTH_TIMEOUT_SECONDS
            )

            if not app_ctx.is_healthy:
                error_msg = _build_registry_unavailable_message(query)
                await ctx.error("Registry API health check failed")
                return {"message": error_msg, "results": []}

        try:
            # Prepare filters for the registry search
            registry_filters = _prepare_registry_filters(include_tags)

            # Use the shared registry client from lifespan context
            found_agents_with_scores: List[Tuple[AgentRegistration, float]] = (
                await app_ctx.registry_client.get_by_capability_semantic(
                    capability_description=query,
                    limit=top_k
                    * 2,  # Fetch more to account for exclusions and filtering
                    similarity_threshold=strictness,
                    filters=registry_filters,
                )
            )

            await ctx.debug(
                f"registry_pre_filter_count={len(found_agents_with_scores)}"
            )

            processed_results = _filter_and_format_results(
                found_agents_with_scores, output_detail, top_k
            )

            await ctx.debug(f"result_count={len(processed_results)}")

            if not processed_results:
                filter_text = f" with tags {include_tags}" if include_tags else ""
                suggestion_text = _build_suggestions(strictness, include_tags)
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
            return {
                "message": "An internal error occurred while searching for agents.",
                "results": [],
            }

    instance = FastMCP(
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
    instance.add_tool(
        fn=search_for_agents_tool,
        name="search_for_agents",
        title="Discover Collaboration Partners",
    )

    return instance


# --- Main Entry Point ---
if __name__ == "__main__":
    import sys

    try:
        mcp = create_agent_discovery_mcp()
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.exit(1)
