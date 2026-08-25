"""
Registry Search Schemas - Single Source of Truth for Agent Search Interfaces

These schemas define the input, output, and result structures for agent search operations.
They are used across all search interfaces: API endpoints, MCP servers, and LangChain tools.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


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
        exclude_none = True


class AgentSearchOutput(BaseModel):
    """Output schema for agent search, containing a list of results."""

    message: str = Field(
        description="A summary message about the search operation (e.g., 'Successfully found X agents', 'No agents matched your criteria', or error details)."
    )
    results: List[AgentSearchResultItem] = Field(
        default_factory=list,
        description="A list of found agents. Each item's detail level is determined by the 'output_detail' input parameter.",
    )

    class Config:
        """Config for the AgentSearchOutput."""

        # Exclude None values during serialization to save tokens and reduce noise
        exclude_none = True

    def __str__(self) -> str:
        """Return a clean JSON string representation without null values."""
        return self.model_dump_json(indent=2, exclude_none=True)
