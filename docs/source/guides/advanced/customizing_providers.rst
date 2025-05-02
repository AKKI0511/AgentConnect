Customizing Providers
=====================

.. _customizing_providers:

Creating Custom AI Providers
-------------------------

This guide explains how to create and use custom AI providers with AgentConnect.

Understanding Providers in AgentConnect
------------------------------------

In AgentConnect, providers are responsible for interfacing with AI services. The framework includes built-in providers for popular services like OpenAI, Anthropic, Google, and Groq, but you can also create custom providers for other services or your own AI models.

Provider Architecture
------------------

Providers in AgentConnect follow a common interface:

1. They extend the `BaseProvider` class
2. They implement methods for generating responses
3. They handle authentication and API communication
4. They convert between AgentConnect's message format and the provider's format

Creating a Custom Provider
-----------------------

To create a custom provider, you need to:

1. Create a new class that extends `BaseProvider`
2. Implement the required methods
3. Handle authentication and API communication
4. Register the provider with the provider factory

Here's an example:

.. code-block:: python

    from abc import ABC, abstractmethod
    from typing import List, Dict, Optional, Any
    from langchain.chat_models import init_chat_model
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain.schema import HumanMessage, AIMessage, SystemMessage
    from agentconnect.core.types import ModelName
    
    class MyCustomProvider(ABC):
        """Custom provider for a hypothetical AI API service."""
        
        def __init__(self, api_key: Optional[str] = None):
            self.api_key = api_key
            self.provider_name = "MyCustomAI"
            self.api_url = "https://api.mycustomai.com/generate"
            
        def _format_messages(self, messages: List[Dict[str, str]]) -> List[Any]:
            """Convert dict messages to LangChain message objects"""
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
            try:
                llm = self.get_langchain_llm(model, **kwargs)
                formatted_messages = self._format_messages(messages)
    
                # Ensure callbacks are passed through
                callbacks = kwargs.get("callbacks", None)
    
                response = await llm.ainvoke(formatted_messages, callbacks=callbacks)
                return response.content
            except Exception as e:
                return f"Provider Error: {str(e)}"
                
        def get_available_models(self) -> List[ModelName]:
            """Return list of available models for this provider"""
            return [
                ModelName.GPT4O,  # Example - replace with actual models
                ModelName.GPT4O_MINI
            ]
            
        def get_langchain_llm(self, model_name: ModelName, **kwargs) -> BaseChatModel:
            """Returns a LangChain chat model instance using init_chat_model"""
            config = {"model": model_name.value, **self._get_provider_config(), **kwargs}
            return init_chat_model(**config)
            
        def _get_provider_config(self) -> Dict[str, Any]:
            """Returns provider-specific configuration"""
            return {
                "api_key": self.api_key,
                "provider": "mycustom",
                "endpoint": self.api_url
            }

Extending the Provider Factory
---------------------------

To make your custom provider available through the provider factory:

.. code-block:: python

    from agentconnect.providers.provider_factory import ProviderFactory
    from agentconnect.core.types import ModelProvider
    from enum import Enum
    
    # Extend the ModelProvider enum
    class CustomModelProvider(str, Enum):
        MYCUSTOM = "mycustom"
    
    # Register your custom provider with the factory
    ProviderFactory._providers[CustomModelProvider.MYCUSTOM] = MyCustomProvider

Using Your Custom Provider
-----------------------

Once you've created and registered your custom provider, you can use it with agents:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import AgentIdentity, InteractionMode
    
    # Create an agent with your custom provider
    agent = AIAgent(
        agent_id="custom-agent-1",
        name="CustomAgent",
        provider_type=CustomModelProvider.MYCUSTOM,  # Your custom provider type
        model_name=ModelName.GPT4O,  # Or your custom model
        api_key="your-api-key",
        identity=AgentIdentity.create_key_based(),
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT
        ]
    )

Advanced Provider Features
-----------------------

You can implement advanced features in your custom provider:

1. **Streaming Responses**: Implement streaming for real-time responses
2. **Model-Specific Parameters**: Add support for model-specific parameters
3. **Rate Limiting**: Implement rate limiting to avoid API throttling
4. **Caching**: Add response caching to improve performance
5. **Fallback Mechanisms**: Implement fallback mechanisms for reliability

Here's an example with streaming support:

.. code-block:: python

    async def generate_streaming_response(
        self, messages: List[Dict[str, str]], model: ModelName, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            formatted_messages = self._format_messages(messages)
            
            # Configure for streaming
            async for chunk in llm.astream(formatted_messages):
                yield chunk.content
        except Exception as e:
            yield f"Provider Error: {str(e)}"

Best Practices
-----------

When creating custom providers, follow these best practices:

1. **Error Handling**: Implement robust error handling for API failures
2. **Logging**: Add detailed logging for debugging
3. **Configuration**: Make the provider configurable for different environments
4. **Testing**: Create tests for your provider
5. **Documentation**: Document your provider's capabilities and usage
6. **Security**: Handle API keys securely
7. **Performance**: Optimize for performance, especially for high-traffic applications 