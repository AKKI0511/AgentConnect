Advanced Configuration Guide
=========================

.. _advanced_configuration:

Configuring AgentConnect for Advanced Use Cases
-------------------------------------------

This guide explains how to configure AgentConnect for advanced use cases, including customizing agent behavior, optimizing communication flows, and implementing security features.

Available Configuration Options
------------------

AgentConnect provides several configuration options that can be customized:

1. **Agent Configuration**: Customize agent behavior and capabilities
2. **Communication Hub Configuration**: Configure message routing and handlers
3. **Provider Configuration**: Set up provider-specific options 
4. **Agent Registry Configuration**: Configure agent discovery and capability matching
5. **Environment Configuration**: Set up environment-specific settings

Agent Configuration
----------------

You can customize agent behavior by configuring various parameters:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import (
        ModelProvider, 
        ModelName, 
        AgentIdentity, 
        InteractionMode,
        Capability
    )
    
    # Create an agent with advanced configuration
    agent = AIAgent(
        agent_id="advanced-agent-1",
        name="AdvancedAssistant",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your-api-key",
        identity=AgentIdentity.create_key_based(),
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT
        ],
        capabilities=[
            Capability(
                name="text_generation",
                description="Generate high-quality text content",
                input_schema={"prompt": "string"},
                output_schema={"text": "string"}
            ),
            Capability(
                name="code_generation",
                description="Generate code in various programming languages",
                input_schema={"language": "string", "task": "string"},
                output_schema={"code": "string"}
            )
        ],
        personality="helpful and informative assistant",
        organization_id="your-org-id",
        # Model-specific parameters
        max_tokens_per_minute = 5500,
        max_tokens_per_hour = 100000,
    )

Communication Hub Configuration
----------------------------

Configure the communication hub for message routing and handling:

.. code-block:: python

    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    
    # Create a registry
    registry = AgentRegistry()
    
    # Create a communication hub
    hub = CommunicationHub(registry)
    
    # Configure message handlers
    async def global_message_handler(message):
        print(f"Global handler received message: {message.id}")
        # Process all messages
    
    hub.add_global_handler(global_message_handler)
    
    # Configure agent-specific message handlers
    async def agent_message_handler(message):
        print(f"Agent handler received: {message.content[:50]}...")
        # Process messages for a specific agent
    
    hub.add_message_handler("agent-id", agent_message_handler)
    
    # Sending a message and waiting for response with timeout
    response = await hub.send_message_and_wait_response(
        sender_id="sender-agent-id",
        receiver_id="receiver-agent-id",
        content="Hello, can you help me with this task?",
        timeout=60  # Wait up to 60 seconds for response
    )

Agent Registry Configuration
---------------------

Configure the agent registry for agent discovery and capability matching:

.. code-block:: python

    from agentconnect.core.registry import AgentRegistry, AgentRegistration
    from agentconnect.core.types import AgentType, AgentIdentity, InteractionMode, Capability
    
    # Create an agent registry
    registry = AgentRegistry()
    
    # Register an agent with the registry
    registration = AgentRegistration(
        agent_id="agent-1",
        organization_id="org-1",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
        capabilities=[
            Capability(
                name="data_analysis",
                description="Analyze and interpret complex datasets",
                input_schema={"data": "array", "analysis_type": "string"},
                output_schema={"results": "object", "insights": "array"}
            )
        ],
        identity=AgentIdentity.create_key_based(),
        owner_id="user-1",
        metadata={"specialization": "financial data"}
    )
    
    # Register the agent
    await registry.register(registration)
    
    # Find agents by capability
    agents_with_capability = await registry.get_by_capability("data_analysis")
    
    # Find agents by semantic capability search
    agents_by_description = await registry.get_by_capability_semantic(
        "Analyze financial market data and provide insights"
    )
    
    # Get all agents
    all_agents = await registry.get_all_agents()

Provider Configuration
-------------------

Configure providers for different AI services:

.. code-block:: python

    from agentconnect.providers.provider_factory import ProviderFactory
    from agentconnect.core.types import ModelProvider, ModelName
    
    # Get a provider instance
    provider = ProviderFactory.create_provider(
        provider_type=ModelProvider.OPENAI,
        api_key="your-api-key"
    )
    
    # Configure provider parameters
    response = await provider.generate_response(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me about AI agents."}
        ],
        model=ModelName.GPT4O,
        temperature=0.7,
        max_tokens=1000
    )

Environment Configuration
---------------------

Configure AgentConnect for different environments:

.. code-block:: python

    import os
    from dotenv import load_dotenv
    
    # Load environment-specific configuration
    load_dotenv()
    
    # Get configuration from environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    # Create environment-specific agent
    env_agent = AIAgent(
        agent_id=os.getenv("AGENT_ID", "agent-1"),
        name=os.getenv("AGENT_NAME", "Assistant"),
        provider_type=ModelProvider.OPENAI,
        model_name=getattr(ModelName, os.getenv("MODEL_NAME", "GPT4O")),
        api_key=api_key,
        identity=AgentIdentity.create_key_based()
    )

.. note::
   Some advanced configuration features mentioned in this guide (such as enhanced security features and performance optimization) are planned for future releases but not fully implemented in the current version.

Configuration Best Practices
-------------------------

Follow these best practices when configuring AgentConnect:

1. **Security First**: Store API keys in environment variables, not in code
2. **Error Handling**: Implement proper error handling for failed operations
3. **Message Handlers**: Use message handlers to monitor and process communication
4. **Scalability**: For high-volume applications, consider using asynchronous patterns
5. **Testing**: Test your configuration in a development environment before production
6. **Documentation**: Document your configuration for team members
7. **Logging**: Enable appropriate logging levels for debugging and monitoring

Example: Complete Configuration
----------------------------

Here's a complete example that demonstrates various configuration options:

.. code-block:: python

    import asyncio
    import logging
    import os
    from dotenv import load_dotenv
    
    from agentconnect.agents import AIAgent, HumanAgent
    from agentconnect.core.types import (
        ModelProvider, 
        ModelName, 
        AgentIdentity, 
        InteractionMode,
        Capability,
        AgentType
    )
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication import CommunicationHub
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("AgentConnect")
    
    # Load environment variables
    load_dotenv()
    
    async def main():
        # Create registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create AI agent
        ai_agent = AIAgent(
            agent_id="ai-assistant",
            name="AI Assistant",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
            identity=AgentIdentity.create_key_based(),
            interaction_modes=[
                InteractionMode.HUMAN_TO_AGENT,
                InteractionMode.AGENT_TO_AGENT
            ],
            capabilities=[
                Capability(
                    name="general_assistant",
                    description="Provide helpful information and assistance on a wide range of topics",
                    input_schema={"query": "string"},
                    output_schema={"response": "string"}
                )
            ],
            personality="helpful and informative",
            organization_id="example-org"
        )
        
        # Create human agent
        human_agent = HumanAgent(
            agent_id="human-user",
            name="Human User",
            identity=AgentIdentity.create_key_based(),
            organization_id="example-org"
        )
        
        # Register agents
        await hub.register_agent(ai_agent)
        await hub.register_agent(human_agent)
        
        # Set up message handler for the AI agent
        async def ai_message_handler(message):
            logger.info(f"AI agent received message: {message.content[:50]}...")
            # Process incoming messages to the AI agent
        
        # Add the message handler
        hub.add_message_handler(ai_agent.agent_id, ai_message_handler)
        
        # Add a global message handler to track all messages
        async def global_message_tracker(message):
            logger.info(f"Message from {message.sender_id} to {message.receiver_id}: {message.content[:30]}...")
        
        hub.add_global_handler(global_message_tracker)
        
        # Start the AI agent
        ai_task = asyncio.create_task(ai_agent.run())
        
        # Send a message from human to AI
        await human_agent.send_message(
            receiver_id=ai_agent.agent_id,
            content="Can you help me with a research question about AI agents?"
        )
        
        # Wait for processing
        await asyncio.sleep(5)
        
        # Clean up
        ai_agent.is_running = False
        await ai_task
        await hub.unregister_agent(ai_agent.agent_id)
        await hub.unregister_agent(human_agent.agent_id)
    
    if __name__ == "__main__":
        asyncio.run(main()) 