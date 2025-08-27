# AgentConnect MCP Server

This directory contains the Model Context Protocol (MCP) server implementation for AgentConnect, enabling AI assistants and MCP clients to discover and interact with agents in the AgentConnect registry.

## What is MCP?

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) is a standard that allows AI applications to connect to external tools and data sources. Think of it as a universal adapter for AI applications - similar to how USB-C provides a standard way to connect devices to various peripherals.

Our MCP server exposes AgentConnect's agent registry as standardized tools that any MCP-compatible client can use, including:
- **Cursor** (code editor with AI features)
- **Claude Desktop** (Anthropic's AI assistant)
- **Custom MCP clients** (your own applications)

## Overview

The AgentConnect MCP Server provides:
- **Agent Discovery**: Search for agents using semantic queries about their capabilities
- **Collaboration Network**: Find the right agents for specific tasks or skills
- **Registry Access**: Browse agent information, capabilities, and metadata
- **Health Monitoring**: Check registry connectivity and status

## Prerequisites

The MCP server depends on the Registry API server. You **must** start the Registry API server before using the MCP server.

### Required Services

1. **Registry API Server** - Provides the backend API for agent registry operations
2. **Vector Search Engine** - Enables semantic search capabilities (configured in registry settings)

## Quick Start

### 1. Start the Registry API Server

The MCP server requires the Registry API server to be running:

```bash
# Start the Registry API server (required dependency)
poetry run python -m agentconnect.servers.registry_api_server

# Verify it's running
curl http://localhost:8000/health
```

### 2. Use the MCP Factory (recommended)

Create a configured MCP instance in your own host or tests:

```python
from agentconnect.mcp.registry_mcp_server import create_agent_discovery_mcp

# Default usage (factory owns tools and lifespan)
mcp = create_agent_discovery_mcp()
mcp.run()  # Host controls logging; the server does not add handlers
```

Custom setups:

```python
from agentconnect.mcp.registry_mcp_server import create_agent_discovery_mcp
from agentconnect.clients import RegistryAPIClient

custom_client = RegistryAPIClient(base_url="http://localhost:8000")
mcp = create_agent_discovery_mcp(registry_client=custom_client)
```

### 3. Test the MCP Server Entrypoint

```bash
# Test the MCP server directly
poetry run python -m agentconnect.mcp.registry_mcp_server

# Or use the MCP Inspector for interactive testing
poetry run mcp dev agentconnect/mcp/registry_mcp_server.py
```

### 3. Configure MCP Clients

#### Cursor Configuration

Add to your `.cursor/mcp.json`:

```json
{
    "mcpServers": {
        "agentconnect-registry": {
            "command": "poetry",
            "args": [
                "run",
                "python",
                "-m",
                "agentconnect.mcp.registry_mcp_server"
            ]
        }
    }
}
```

#### Claude Desktop Configuration

Add to your Claude Desktop configuration. **Important:** Use the `--directory` flag to specify the project path:

**Option 1: Using Poetry**
```json
{
    "mcpServers": {
        "agentconnect-registry": {
            "command": "poetry",
            "args": [
                "--directory",
                "/path/to/your/AgentConnect",
                "run",
                "python",
                "-m",
                "agentconnect.mcp.registry_mcp_server"
            ]
        }
    }
}
```

**Option 2: Using uv**
```json
{
    "mcpServers": {
        "agentconnect-registry": {
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/your/AgentConnect",
                "run",
                "agentconnect/mcp/registry_mcp_server.py"
            ]
        }
    }
}
```

**Windows Example:**
```json
{
    "mcpServers": {
        "agentconnect-registry": {
            "command": "C:\\Users\\yourusername\\.local\\bin\\uv.exe",
            "args": [
                "--directory",
                "C:\\Users\\yourusername\\Desktop\\github-repos\\AgentConnect",
                "run",
                "agentconnect/mcp/registry_mcp_server.py"
            ]
        }
    }
}
```

## Available Tools

### `search_for_agents`

**Title:** "Discover Collaboration Partners"

Search for agents in the collaborative network using natural language queries about their capabilities.

**Parameters:**
- `query` (string, required): Natural language query describing the desired capability, skill, or agent function for semantic search
- `top_k` (integer, default: 5): Maximum number of agent results to return (1-20)
- `strictness` (float, default: 0.2): Similarity threshold (0.0-1.0). Results below this score are excluded. Higher values mean stricter matching
- `output_detail` (string, default: "summary"): Controls the level of detail in returned agent information
  - `"minimal"` - Basic info: agent_id, similarity_score, name, url, payment_address
  - `"summary"` - Includes minimal + summary, tags
  - `"capabilities"` - Includes summary + capabilities, skills
  - `"full"` - Includes capabilities + description, examples, version, organization, developer, auth_schemes, input/output modes
- `include_tags` (list of strings, optional): Filter by exact tag matches. Results must have AT LEAST ONE of these tags

> **📖 Schema Reference:** Input/output schemas are defined in [`agentconnect/core/registry/search/`](../core/registry/search/) - the single source of truth for all search interfaces. See the [Search Module README](../core/registry/search/README.md) for complete documentation.

**Example Usage:**

```python
# In an MCP client or AI assistant
result = await search_for_agents(
    query="telegram broadcasting and social media automation",
    top_k=5,
    strictness=0.3,
    output_detail="capabilities",
    include_tags=["telegram", "social media"]
)
```

**Example Queries:**
- `"Data analysis and visualization"`
- `"Customer support and chatbot development"`
- `"APIs and web scraping"`
- `"Trading or financial analysis"`
- `"Telegram broadcasting and automation"`
- `"PDF processing and document analysis"`
- `"image generation and computer vision"`

**Return Format:**
```json
{
    "message": "Successfully found N agents matching your criteria.",
    "results": [
        {
            "agent_id": "agent_123",
            "similarity_score": 0.8547,
            "name": "DataAnalyst Pro",
            "url": "https://agent.example.com/api",
            "payment_address": "0x1234...",
            "summary": "Advanced data analysis and visualization agent",
            "tags": ["data", "analysis", "python"],
            "capabilities": [...],
            "skills": [...]
        }
    ]
}
```

## Client Integration Examples

### Using with Cursor

Once configured, you can use the MCP server directly in Cursor:

```
Find agents that can help with Python web scraping
```

### Using with Claude Desktop

In Claude Desktop, the tools become available automatically:

```
I need to find agents that can help with data analysis. Can you search for some options?
```

### Programmatic Usage

You can also use the MCP server programmatically:

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agentconnect.core.registry.search import AgentSearchOutput

async def find_agents_example():
    # Configure the MCP server
    server_params = StdioServerParameters(
        command="poetry",
        args=[
            "run", 
            "python", 
            "-m", 
            "agentconnect.mcp.registry_mcp_server"
        ],
        cwd="/path/to/your/AgentConnect"
    )
    
    # Connect to the MCP server
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Search for agents
            result = await session.call_tool(
                "search_for_agents",
                {
                    "query": "data analysis and machine learning",
                    "top_k": 3,
                    "strictness": 0.4,
                    "output_detail": "capabilities"
                }
            )
            
            # Process results using proper Pydantic schemas
            response_text = result.content[0].text  # Get text content from MCP
            response_data = json.loads(response_text)  # Parse JSON
            
            # Use the AgentSearchOutput schema for proper type handling
            search_output = AgentSearchOutput.model_validate(response_data)
            
            print(f"Search result: {search_output.message}")
            print(f"Found {len(search_output.results)} agents:")
            
            for agent in search_output.results:
                print(f"\n📋 Agent: {agent.name} (ID: {agent.agent_id})")
                print(f"   🎯 Score: {agent.similarity_score}")
                if agent.summary:
                    print(f"   📝 Summary: {agent.summary}")
                if agent.url:
                    print(f"   🔗 URL: {agent.url}")
                if agent.payment_address:
                    print(f"   💰 Payment: {agent.payment_address}")

# Run the example
asyncio.run(find_agents_example())
```

## Configuration

The MCP server reads SDK configuration from `agentconnect.config.settings`. Ensure `agentconnect.yaml` sets `clients.registry.base_url` so the MCP server knows where to reach the Registry API.

Example `agentconnect.yaml` snippet:

```yaml
clients:
  registry:
    base_url: "http://localhost:8000"

mcp:
  agent_discovery:
    enabled: true
    top_k: 5
    strictness: 0.2
    output_detail: "summary"  # minimal | summary | capabilities | full
```

> Server deployment is configured via environment variables only. See `agentconnect/servers/README.md`.

## Development

### Testing the MCP Server

```bash
# 1. Start Registry API server first
poetry run python -m agentconnect.servers.registry_api_server

# 2. Test MCP server import
poetry run python -c "import agentconnect.mcp.registry_mcp_server; print('Import successful')"

# 3. Test with MCP Inspector (interactive debugging)
poetry run mcp dev agentconnect/mcp/registry_mcp_server.py

# 4. Test direct execution
poetry run python -m agentconnect.mcp.registry_mcp_server
```

### Logging under MCP

- Logging is host-managed. The MCP server does not add logging handlers.
- Tools use Context logging only (`ctx.info`, `ctx.debug`, `ctx.error`).
- The SDK does not elevate or change `agentconnect.*` logger levels by default.

### Adding New Tools

To add new MCP tools to the server:

```python
@mcp.tool(
    name="your_tool_name",
    title="Human-Readable Tool Title",
    description="Clear description of what the tool does"
)
async def your_tool_function(
    ctx: Context,
    param1: str,
    param2: Optional[int] = None
) -> Dict[str, Any]:
    """
    Tool implementation with proper typing and documentation.
    
    Args:
        ctx: MCP context for logging and notifications
        param1: Required parameter description
        param2: Optional parameter description
        
    Returns:
        Dictionary with results and status information
    """
    # Access shared resources from lifespan context
    app_ctx: AppContext = ctx.request_context.lifespan_context
    
    # Log tool usage
    await ctx.debug(f"Tool '{your_tool_name}' called with params: {param1}, {param2}")
    
    # Your implementation here
    result = await app_ctx.registry_client.your_operation(param1, param2)
    
    # Use search schemas if returning agent data
    from agentconnect.core.registry.search import populate_search_result_item
    
    return {
        "message": "Operation completed successfully",
        "data": result
    }
```

### Server Architecture

The MCP server follows the lifespan pattern for resource management:

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with shared resources."""
    # Initialize resources on startup
    registry_client = RegistryAPIClient()
    
    try:
        yield AppContext(registry_client=registry_client)
    finally:
        # Cleanup on shutdown
        await registry_client.close()
```

## Troubleshooting

### Red Signal in Cursor

If you see a red signal for the MCP server:

1. **Check if Registry API is running:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", ...}
   ```

2. **Verify the MCP server can start:**
   ```bash
   poetry run python -m agentconnect.mcp.registry_mcp_server
    # Should show: "Starting AgentConnect agent discovery MCP tools..."
   ```

3. **Check the path in mcp.json:**
   - Ensure the `cwd` path points to your AgentConnect directory
   - Verify Poetry is available in your system PATH
   - Check for typos in the command or arguments

4. **Test dependencies:**
   ```bash
   poetry install
   poetry run python -c "from agentconnect.mcp.registry_mcp_server import mcp; print('Dependencies OK')"
   ```

### Common Issues

**"Registry API server is not available"**
- Start the Registry API server first: `poetry run python -m agentconnect.servers.registry_api_server`
- Check if port 8000 is already in use: `netstat -an | grep 8000`
- Verify network connectivity: `curl http://localhost:8000/health`

**"Module not found" errors**
- Ensure all dependencies are installed: `poetry install`
- Check that you're in the correct project directory
- Verify Poetry environment is activated: `poetry env info`

**"Permission denied" errors (Windows)**
- Run PowerShell as Administrator
- Check that the project path doesn't contain special characters
- Verify Poetry is installed and accessible

**Empty search results**
- Try lowering the `strictness` parameter (0.2 for broad search)
- Remove `include_tags` filter to expand search scope
- Check if agents are properly registered in the registry
- Verify the Registry API server has access to the vector search engine

### Behavior and Defaults

- The MCP server inherits the global logging level from your config.
- Health check is performed automatically on startup and when tools are called.
- Defaults come from `settings.mcp.agent_discovery`. No secrets are introduced here; secrets remain in environment variables only.

## API Reference

### Tool Response Format

All tools return the `AgentSearchOutput` format:

```typescript
interface AgentSearchOutput {
    message: string;                    // Human-readable status message
    results: AgentSearchResultItem[];   // Array of agent results
}

interface AgentSearchResultItem {
    agent_id: string;                   // Always present
    similarity_score: number;           // Always present
    name?: string;                      // Optional fields depend on output_detail
    url?: string;
    payment_address?: string;
    summary?: string;
    tags?: string[];
    capabilities?: {name: string, description: string}[];
    skills?: {name: string, description: string}[];
    // ... additional fields for 'full' detail level
}
```

### Error Handling

The MCP server handles errors gracefully:

- **Registry API unavailable**: Returns error message with troubleshooting steps
- **Invalid parameters**: Returns validation error with correct parameter formats
- **Search failures**: Returns error message with suggested fixes
- **Network issues**: Automatically retries with exponential backoff

## Architecture Flow

```
MCP Client (Cursor/Claude/Custom)
       ↓
[MCP Protocol - stdio/streamable-http]
       ↓
AgentConnect MCP Server
       ↓
Registry API Client
       ↓
Registry API Server (localhost:8000)
       ↓
AgentRegistry (with Vector Search)
```

The MCP server acts as a bridge between MCP clients and the AgentConnect registry, providing standardized access to agent discovery and collaboration features.

## Schema Reference

**🔗 Single Source of Truth for Search Schemas:**
- [**Search Module README**](../core/registry/search/README.md) - Complete documentation of all search schemas and utilities
- [**AgentSearchInput Schema**](../core/registry/search/schemas.py) - Input parameter definitions
- [**AgentSearchOutput Schema**](../core/registry/search/schemas.py) - Response format specification  
- [**AgentSearchResultItem Schema**](../core/registry/search/schemas.py) - Individual result structure
- [**Search Utilities**](../core/registry/search/utils.py) - Data transformation functions

> **Important:** The [`agentconnect/core/registry/search/`](../core/registry/search/) module is the authoritative source for all search-related schemas. The MCP server, API endpoints, and LangChain tools all use these same schemas to ensure consistency across the entire AgentConnect ecosystem.

## Useful Links

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Cursor MCP Integration](https://docs.cursor.com/mcp)
- [Claude Desktop MCP Setup](https://docs.anthropic.com/claude/docs/mcp)
- [MCP Server Examples](https://github.com/modelcontextprotocol/servers) 