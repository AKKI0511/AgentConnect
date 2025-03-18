"""
Groq provider implementation for the AgentConnect framework.

This module provides the Groq provider implementation, which allows
agents to generate responses using Groq's hosted models.
"""

# Standard library imports
import os
from typing import Any, Dict, List

# Absolute imports from agentconnect package
from agentconnect.core.types import ModelName
from agentconnect.providers.base_provider import BaseProvider


class GroqProvider(BaseProvider):
    """
    Provider implementation for Groq models.

    This class provides access to Groq's hosted models, including
    Llama, Mixtral, and Gemma models.

    Attributes:
        api_key: Groq API key
    """

    def __init__(self, api_key: str):
        """
        Initialize the Groq provider.

        Args:
            api_key: Groq API key
        """
        super().__init__(api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.MIXTRAL,
        **kwargs,
    ) -> str:
        """
        Generate a response using a Groq-hosted model.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: The Groq model to use
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
            return f"Groq Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        """
        Get a list of available Groq models.

        Returns:
            List of available Groq model names
        """
        return [
            ModelName.LLAMA33_70B_VTL,
            ModelName.LLAMA3_1_8B_INSTANT,
            ModelName.LLAMA3_70B,
            ModelName.LLAMA3_8B,
            ModelName.LLAMA_GUARD3_8B,
            ModelName.MIXTRAL,
            ModelName.GEMMA2_90B,
        ]

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get Groq-specific configuration.

        Returns:
            Dictionary of Groq-specific configuration
        """
        return {"groq_api_key": self.api_key, "model_provider": "groq"}


if __name__ == "__main__":
    provider = GroqProvider(os.getenv("GROQ_API_KEY"))
    print(provider.get_available_models())
