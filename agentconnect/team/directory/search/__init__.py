"""
Registry Search Subdomain - Agent Search Interfaces and Utilities

This module provides schemas and utilities specifically for agent search operations.
It serves as the interface layer between the registry domain and external consumers
(API servers, MCP servers, LangChain tools, etc.).
"""

from agentconnect.team.directory.search.schemas import (
    AgentSearchInput,
    AgentSearchOutput,
    AgentSearchResultItem,
)
from agentconnect.team.directory.search.utils import (
    format_capabilities_for_output,
    format_skills_for_output,
    populate_search_result_item,
)

# Define public API
__all__ = [
    # Schemas
    "AgentSearchInput",
    "AgentSearchOutput",
    "AgentSearchResultItem",
    # Utilities
    "format_capabilities_for_output",
    "format_skills_for_output",
    "populate_search_result_item",
]
