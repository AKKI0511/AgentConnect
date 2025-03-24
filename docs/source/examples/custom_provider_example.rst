Custom Provider Example
=====================

.. _custom_provider_example:

Creating a Custom Provider
------------------------

This example demonstrates how to create and use a custom AI provider with AgentConnect.

Implementing a Custom Provider
----------------------------

You can extend the BaseProvider class to create a custom provider for any AI service:

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

Using the Custom Provider
-----------------------

Once you've implemented your custom provider, you can use it with agents:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, InteractionMode
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    
    # Create an agent registry and communication hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create an identity for your agent
    identity = AgentIdentity.create_key_based()
    
    # Initialize your custom provider
    custom_provider = MyCustomProvider(api_key="your-api-key")
    
    # Create an agent with your custom provider
    agent = AIAgent(
        agent_id="custom-agent-1",
        name="CustomAgent",
        provider_type=ModelProvider.OPENAI,  # You would need to extend ModelProvider enum
        model_name=ModelName.GPT4O,
        api_key="your-api-key",
        identity=identity,
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT
        ]
    )
    
    # Register the agent with the hub
    await hub.register_agent(agent)
    
    # Use the agent
    # You would typically interact with the agent through the hub

Extending the Provider Factory
--------------------------

You can also extend the provider factory to support your custom provider:

.. code-block:: python

    from agentconnect.providers.provider_factory import ProviderFactory
    from agentconnect.core.types import ModelProvider
    from enum import Enum
    
    # Extend the ModelProvider enum
    class CustomModelProvider(str, Enum):
        MYCUSTOM = "mycustom"
    
    # Register your custom provider with the factory
    ProviderFactory._providers[CustomModelProvider.MYCUSTOM] = MyCustomProvider
    
    # Create a provider using the factory
    provider = ProviderFactory.create_provider(
        provider_type=CustomModelProvider.MYCUSTOM,
        api_key="your-api-key"
    ) 