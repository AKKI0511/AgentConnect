"""
Google provider implementation for the AgentConnect framework.

This module provides the Google provider implementation, which allows
agents to generate responses using Google's Gemini models.
"""

# Standard library imports
import os
from typing import Any, Dict, List

# Absolute imports from agentconnect package
from agentconnect.core.types import ModelName
from agentconnect.providers.base_provider import BaseProvider


class GoogleProvider(BaseProvider):
    """
    Provider implementation for Google Gemini models.

    This class provides access to Google's Gemini models, including
    Gemini 1.5 and Gemini 2.0 variants.

    Attributes:
        api_key: Google AI API key
    """

    def __init__(self, api_key: str):
        """
        Initialize the Google provider.

        Args:
            api_key: Google AI API key
        """
        super().__init__(api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.GEMINI1_5_FLASH,
        **kwargs,
    ) -> str:
        """
        Generate a response using a Google Gemini model.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: The Gemini model to use
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
            return f"Google AI Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        """
        Get a list of available Google Gemini models.

        Returns:
            List of available Gemini model names
        """
        return [
            ModelName.GEMINI2_5_PRO_PREVIEW,
            ModelName.GEMINI2_5_PRO_EXP,
            ModelName.GEMINI2_FLASH,
            ModelName.GEMINI2_FLASH_LITE,
            ModelName.GEMINI1_5_FLASH,
            ModelName.GEMINI1_5_PRO,
            ModelName.GEMINI2_FLASH_THINKING_EXP,
            ModelName.GEMINI2_PRO_EXP,
        ]

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get Google-specific configuration.

        Returns:
            Dictionary of Google-specific configuration
        """
        return {"gemini_api_key": self.api_key, "model_provider": "google_genai"}


if __name__ == "__main__":
    provider = GoogleProvider(os.getenv("GOOGLE_API_KEY"))
    print(provider.get_available_models())
