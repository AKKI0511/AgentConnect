"""
Anthropic provider implementation for the AgentConnect framework.

This module provides the Anthropic provider implementation, which allows
agents to generate responses using Anthropic's Claude models.
"""

# Standard library imports
import os
from typing import Any, Dict, List

# Third-party imports
import anthropic
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

# Absolute imports from agentconnect package
from agentconnect.core.types import ModelName
from agentconnect.providers.base_provider import BaseProvider


class AnthropicProvider(BaseProvider):
    """
    Provider implementation for Anthropic Claude models.

    This class provides access to Anthropic's Claude models, including
    Claude 3 Opus, Sonnet, and Haiku variants.

    Attributes:
        api_key: Anthropic API key
        client: Anthropic client instance
    """

    def __init__(self, api_key: str):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
        """
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.CLAUDE_3_5_HAIKU,
        **kwargs,
    ) -> str:
        """
        Generate a response using an Anthropic Claude model.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: The Claude model to use
            **kwargs: Additional arguments to pass to the model

        Returns:
            Generated response text

        Raises:
            Exception: If there is an error generating the response
        """
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            return f"Anthropic Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        """
        Get a list of available Anthropic Claude models.

        Returns:
            List of available Claude model names
        """
        return [
            ModelName.CLAUDE_3_7_SONNET,
            ModelName.CLAUDE_3_5_SONNET,
            ModelName.CLAUDE_3_5_HAIKU,
            ModelName.CLAUDE_3_OPUS,
            ModelName.CLAUDE_3_SONNET,
            ModelName.CLAUDE_3_HAIKU,
        ]

    def get_langchain_llm(self, model_name: ModelName, **kwargs) -> BaseChatModel:
        """
        Get a LangChain chat model instance for Anthropic.

        Args:
            model_name: Name of the Claude model to use
            **kwargs: Additional arguments to pass to the model

        Returns:
            LangChain chat model instance for Anthropic
        """
        return ChatAnthropic(model=model_name.value, api_key=self.api_key, **kwargs)

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get Anthropic-specific configuration.

        Returns:
            Dictionary of Anthropic-specific configuration
        """
        return {"anthropic_api_key": self.api_key, "model_provider": "anthropic"}


if __name__ == "__main__":
    provider = AnthropicProvider(os.getenv("ANTHROPIC_API_KEY"))
    print(provider.get_available_models())
