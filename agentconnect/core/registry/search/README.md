# Registry Search Module

The Registry Search module provides standardized schemas and utilities for agent search operations across all AgentConnect interfaces. This module serves as the interface layer between the registry domain and external consumers (API servers, MCP servers, LangChain tools, etc.).

## Directory Structure

```
search/
├── __init__.py          # Package exports and public API
├── schemas.py           # Pydantic schemas for search input/output
├── utils.py             # Utility functions for data transformation
└── README.md            # This file
```

## Overview

This module establishes a **Single Source of Truth** for agent search interfaces, ensuring consistency across all search implementations in AgentConnect. It provides:

- **Standardized input/output schemas** for all search operations
- **Flexible detail levels** to control response verbosity
- **Utility functions** for transforming registry data to search results
- **Type safety** through Pydantic models

## Core Components

### 1. `schemas.py` - Search Data Structures

Defines three main Pydantic models:

#### `AgentSearchInput`
Input schema for agent search operations with the following fields:
- `query` (str): Natural language query for semantic search
- `top_k` (int): Maximum number of results to return (1-20, default 5)
- `strictness` (float): Similarity threshold (0.0-1.0, default 0.2)
- `output_detail` (str): Detail level - "minimal", "summary", "capabilities", or "full"
- `include_tags` (Optional[List[str]]): Filter by exact tag matches

#### `AgentSearchResultItem`
Represents a single agent in search results with hierarchical detail levels:

**Minimal Level:**
- `agent_id`, `similarity_score`, `name`, `url`, `payment_address`

**Summary Level (includes minimal):**
- `summary`, `tags`

**Capabilities Level (includes summary):**
- `capabilities`, `skills`

**Full Level (includes capabilities):**
- `description`, `examples`, `version`, `organization`, `developer`, `auth_schemes`, `default_input_modes`, `default_output_modes`

#### `AgentSearchOutput`
Output schema containing:
- `message` (str): Summary of search operation
- `results` (List[AgentSearchResultItem]): List of found agents

### 2. `utils.py` - Data Transformation Utilities

Provides functions for converting registry domain objects to search interface objects:

#### `format_capabilities_for_output(cap_list)`
Converts `List[Capability]` to `List[Dict[str, str]]` with "name" and "description" keys.

#### `format_skills_for_output(skill_list)`
Converts `List[Skill]` to `List[Dict[str, str]]` with "name" and "description" keys.

#### `populate_search_result_item(registration, similarity_score, output_detail_level)`
**Core utility** that transforms `AgentRegistration` objects into `AgentSearchResultItem` objects based on the requested detail level. This function:
- Respects the hierarchical detail levels
- Handles optional fields gracefully
- Rounds similarity scores to 4 decimal places
- Excludes None values to reduce response size

## Usage Examples

### Basic Search with Different Detail Levels

```python
from agentconnect.core.registry.search import (
    AgentSearchInput, 
    populate_search_result_item
)

# Create search input
search_input = AgentSearchInput(
    query="agent that can analyze data",
    top_k=10,
    strictness=0.3,
    output_detail="capabilities",
    include_tags=["data", "analysis"]
)

# Transform registry result to search result
search_result = populate_search_result_item(
    registration=agent_registration,
    similarity_score=0.85,
    output_detail_level="capabilities"
)
```

### Working with Search Results

```python
from agentconnect.core.registry.search import AgentSearchOutput

# Create output with results
output = AgentSearchOutput(
    message="Found 3 agents matching your criteria",
    results=[result1, result2, result3]
)

# Get clean JSON representation
json_output = output.model_dump_json(exclude_none=True)
```

## Integration Points

This module is used by:

1. **API Servers** (`agentconnect/servers/`)
   - REST endpoints for agent search
   - Consistent request/response format

2. **MCP Servers** (`agentconnect/mcp/`)
   - Model Context Protocol implementations
   - Standardized tool interfaces

3. **LangChain Tools** (`agentconnect/prompts/custom_tools/`)
   - Agent search tools for LLM workflows
   - Consistent output formatting

4. **Registry Base** (`agentconnect/core/registry/`)
   - Internal search result formatting
   - Unified interface for all search operations

## Design Principles

### 1. Single Source of Truth
All search interfaces use these schemas, ensuring consistency across the entire system.

### 2. Hierarchical Detail Levels
The detail level system allows consumers to request only the information they need:
- **Minimal**: For quick lookups or UI lists
- **Summary**: For overview displays
- **Capabilities**: For capability matching
- **Full**: For complete agent profiles

### 3. Type Safety
Pydantic models provide runtime validation and IDE support for all search operations.

### 4. Extensibility
The schema structure allows for easy addition of new fields without breaking existing consumers.

### 5. Performance Optimization
- `exclude_none=True` reduces response payload size
- Similarity scores are rounded to reduce precision noise
- Optional fields prevent unnecessary data transfer

## Configuration

No direct configuration is required for this module. It relies on:
- Registry configuration for underlying search operations
- Consumer-specific settings for detail levels and filtering

## Dependencies

- `pydantic`: For schema validation and serialization
- `typing`: For type hints and annotations
- `agentconnect.core.registry.registration`: For domain object types

## Error Handling

The schemas include validation rules:
- `top_k`: Must be between 1-20
- `strictness`: Must be between 0.0-1.0  
- `output_detail`: Must be one of the valid detail levels
- Pattern validation for specific fields

Invalid inputs will raise Pydantic validation errors with descriptive messages.

## Future Enhancements

Planned improvements include:
- Additional filtering options (by organization, capabilities, etc.)
- Support for sorting options
- Enhanced metadata in search results
- Caching hints for frequently accessed data 