"""
AgentConnect MCP (Model Context Protocol) Package

This package provides MCP server implementations for AgentConnect services,
enabling integration with MCP-compatible clients like Cursor, Claude Desktop, and other AI tools.

Available MCP Servers:

- registry_mcp_server: MCP server for agent registry search operations

MCP Protocol:
The Model Context Protocol (MCP) is a standard for connecting AI models with external tools and data sources.
These servers expose AgentConnect registry functionality as MCP tools that can be used by compatible AI assistants.
"""

# Note: We don't import the actual server instances here since they are meant to be run standalone
# Import only the modules for programmatic access if needed

# Export module references for advanced usage
__all__ = [
    # Module names - users can import the modules directly if needed
    "registry_mcp_server",
]

# Version and metadata
__description__ = "AgentConnect MCP server implementations"

# Usage information
__usage__ = """
To run MCP servers:

Basic Registry MCP Server:
    python -m agentconnect.mcp.registry_mcp_server

These servers communicate via stdio and are designed to be used with MCP-compatible clients.
"""
