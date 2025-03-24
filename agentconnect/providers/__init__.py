"""
Provider implementations for the AgentConnect framework.

This module provides various model providers that can be used by AI agents,
including support for OpenAI, Anthropic, Groq, and Google AI models. The module
implements a factory pattern for creating provider instances based on the
desired model provider.

Key components:

- **ProviderFactory**: Factory class for creating provider instances
- **BaseProvider**: Abstract base class for all providers
- **Specific providers**: OpenAI, Anthropic, Groq, Google
"""

from agentconnect.providers.anthropic_provider import AnthropicProvider

# Base provider class
from agentconnect.providers.base_provider import BaseProvider
from agentconnect.providers.google_provider import GoogleProvider
from agentconnect.providers.groq_provider import GroqProvider

# Specific provider implementations
from agentconnect.providers.openai_provider import OpenAIProvider

# Provider factory for creating provider instances
from agentconnect.providers.provider_factory import ProviderFactory

__all__ = [
    # Factory
    "ProviderFactory",
    # Base class
    "BaseProvider",
    # Provider implementations
    "OpenAIProvider",
    "AnthropicProvider",
    "GroqProvider",
    "GoogleProvider",
]
