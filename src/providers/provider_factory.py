from typing import Dict, Type
from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .groq_provider import GroqProvider
from .google_provider import GoogleProvider
from src.core.types import ModelProvider


class ProviderFactory:
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
        provider_class = cls._providers.get(provider_type)
        if not provider_class:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        return provider_class(api_key)
