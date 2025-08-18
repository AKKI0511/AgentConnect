"""
AgentConnect Configuration System

This module provides a comprehensive, developer-friendly configuration system for AgentConnect
that follows industry best practices from frameworks like LangChain and CrewAI.

Key features:

- Sane defaults that work out of the box
- Single global settings object with nested models
- Three-tier precedence: runtime kwargs > agentconnect.yaml > defaults
- Minimal YAML exposure - only essential developer-facing settings
- Environment variables are reserved for secrets and read by subsystems directly, not by the global settings

Usage:
    .. code-block:: python

        from agentconnect.config import settings, load_settings

        # Access nested configuration
        registry_config = settings.registry.vector_search
        client_config = settings.clients.registry

        # Override at runtime
        custom_settings = load_settings(registry={'vector_search': {'in_memory': False}})
"""

from agentconnect.config.loaders import load_settings
from agentconnect.config.models import AgentConnectSettings

# Global settings instance - this is the main export
settings = load_settings()

# Public API
__all__ = [
    "settings",
    "load_settings",
    "AgentConnectSettings",
]
