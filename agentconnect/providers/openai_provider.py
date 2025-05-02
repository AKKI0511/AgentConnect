"""
OpenAI provider implementation for the AgentConnect framework.

This module provides the OpenAI provider implementation, which allows
agents to generate responses using OpenAI's language models.
"""

# Standard library imports
import os
from typing import Any, Dict, List

# Absolute imports from agentconnect package
from agentconnect.core.types import ModelName
from agentconnect.providers.base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    """
    Provider implementation for OpenAI models.

    This class provides access to OpenAI's language models, including
    GPT-4o, GPT-4.5, and o1 models.

    Attributes:
        api_key: OpenAI API key
    """

    def __init__(self, api_key: str):
        """
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
        """
        super().__init__(api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.GPT4O_MINI,
        **kwargs,
    ) -> str:
        """
        Generate a response using an OpenAI model.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: The OpenAI model to use
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
            return f"OpenAI Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        """
        Get a list of available OpenAI models.

        Returns:
            List of available OpenAI model names
        """
        return [
            ModelName.GPT4_5_PREVIEW,
            ModelName.GPT4_1,
            ModelName.GPT4_1_MINI,
            ModelName.GPT4O,
            ModelName.GPT4O_MINI,
            ModelName.O1,
            ModelName.O1_MINI,
            ModelName.O3,
            ModelName.O3_MINI,
            ModelName.O4_MINI,
        ]

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get OpenAI-specific configuration.

        Returns:
            Dictionary of OpenAI-specific configuration
        """
        return {"openai_api_key": self.api_key, "model_provider": "openai"}


if __name__ == "__main__":
    provider = OpenAIProvider(os.getenv("OPENAI_API_KEY"))
    print(provider.get_available_models())
