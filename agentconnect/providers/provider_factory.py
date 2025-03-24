"""
Provider factory for the AgentConnect framework.

This module provides a factory class for creating provider instances based on
the desired model provider, implementing the factory pattern for provider creation.
"""

# Standard library imports
import logging
from typing import Dict, Type

# Absolute imports from agentconnect package
from agentconnect.core.types import ModelProvider
from agentconnect.providers.anthropic_provider import AnthropicProvider
from agentconnect.providers.base_provider import BaseProvider
from agentconnect.providers.google_provider import GoogleProvider
from agentconnect.providers.groq_provider import GroqProvider
from agentconnect.providers.openai_provider import OpenAIProvider

# Set up logging
logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Factory class for creating provider instances.

    This class implements the factory pattern for creating provider instances
    based on the desired model provider.

    Attributes:
        _providers: Dictionary mapping provider types to provider classes
    """

    _providers: Dict[ModelProvider, Type[BaseProvider]] = {
        ModelProvider.OPENAI: OpenAIProvider,
        ModelProvider.ANTHROPIC: AnthropicProvider,
        ModelProvider.GROQ: GroqProvider,
        ModelProvider.GOOGLE: GoogleProvider,
    }

    @classmethod
    def create_provider(
        cls, provider_type: ModelProvider, api_key: str
    ) -> BaseProvider:
        """
        Create a provider instance.

        Args:
            provider_type: Type of provider to create
            api_key: API key for the provider

        Returns:
            Provider instance

        Raises:
            ValueError: If the provider type is not supported
        """
        provider_class = cls._providers.get(provider_type)
        if not provider_class:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        return provider_class(api_key)

    @classmethod
    def get_available_providers(cls) -> Dict[str, Dict]:
        """
        Get all available providers and their models.

        Returns:
            Dictionary mapping provider names to provider information
        """
        providers = {}
        for provider_type, provider_class in cls._providers.items():
            try:
                # Create an instance with an empty API key just to get the models
                provider_instance = provider_class("")
                providers[provider_type.value] = {
                    "name": provider_type.value.title(),
                    "models": provider_instance.get_available_models(),
                }
            except Exception as e:
                # Skip providers that fail to initialize
                logger.error(f"Failed to initialize provider: {provider_type}")
                logger.error(f"Error: {e}")
                continue
        return providers
