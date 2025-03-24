"""
Base provider implementation for the AgentConnect framework.

This module provides the abstract base class for all model providers,
defining the core functionality for generating responses from language models.
"""

# Standard library imports
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Third-party imports
from langchain.chat_models import init_chat_model
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

# Absolute imports from agentconnect package
from agentconnect.core.types import ModelName


class BaseProvider(ABC):
    """
    Abstract base class for all model providers.

    This class defines the interface that all model providers must implement,
    including methods for generating responses, getting available models,
    and configuring the provider.

    Attributes:
        api_key: API key for the provider
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the provider with an API key.

        Args:
            api_key: API key for the provider
        """
        self.api_key = api_key

    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Any]:
        """
        Convert dictionary messages to LangChain message objects.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys

        Returns:
            List of LangChain message objects
        """
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                formatted_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                formatted_messages.append(AIMessage(content=msg["content"]))
        return formatted_messages

    async def generate_response(
        self, messages: List[Dict[str, str]], model: ModelName, **kwargs
    ) -> str:
        """
        Generate a response from the language model.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: The model to use for generation
            **kwargs: Additional arguments to pass to the model

        Returns:
            Generated response text

        Raises:
            Exception: If there is an error generating the response
        """
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            formatted_messages = self._format_messages(messages)

            # Ensure callbacks are passed through
            callbacks = kwargs.get("callbacks", None)

            response = await llm.ainvoke(formatted_messages, callbacks=callbacks)
            return response.content
        except Exception as e:
            return f"Provider Error: {str(e)}"

    @abstractmethod
    def get_available_models(self) -> List[ModelName]:
        """
        Get a list of available models for this provider.

        Returns:
            List of available model names
        """
        pass

    def get_langchain_llm(self, model_name: ModelName, **kwargs) -> BaseChatModel:
        """
        Get a LangChain chat model instance.

        Args:
            model_name: Name of the model to use
            **kwargs: Additional arguments to pass to the model

        Returns:
            LangChain chat model instance
        """
        config = {"model": model_name.value, **self._get_provider_config(), **kwargs}
        return init_chat_model(**config)

    @abstractmethod
    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get provider-specific configuration.

        Returns:
            Dictionary of provider-specific configuration
        """
        pass


if __name__ == "__main__":
    provider = BaseProvider()
    print(provider.get_available_models())
