"""
AgentConnect Servers Package

This package provides server implementations for AgentConnect services,
offering RESTful APIs and service endpoints for distributed agent management.

Available Servers:
- RegistryAPIServer: FastAPI-based REST API for agent registry operations
"""

from agentconnect.servers.registry_api_server import app as registry_api_app

# Export the main FastAPI application
__all__ = [
    "registry_api_app",
]

# Version and metadata
__description__ = "AgentConnect server implementations"
