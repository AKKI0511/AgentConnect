"""
AgentConnect Clients Package

This package provides client implementations for interacting with AgentConnect services,
offering both low-level API access and high-level abstractions for remote agent management.

Available Clients:

- RegistryAPIClient: HTTP client for AgentConnect Registry API Server
"""

from agentconnect.clients.registry_client import RegistryAPIClient

# Export the main client class
__all__ = [
    "RegistryAPIClient",
]

# Version and metadata
__description__ = "AgentConnect client implementations"
