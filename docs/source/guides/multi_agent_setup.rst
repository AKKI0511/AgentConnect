Multi-Agent Setup Guide
=====================

.. _multi_agent_setup:

Setting Up Multiple Agents
-----------------------

This guide explains how to set up and manage multiple agents in AgentConnect.

Prerequisites
-----------

Before setting up multiple agents, ensure you have:

- Installed AgentConnect
- API keys for the AI providers you plan to use
- Basic understanding of the AgentConnect architecture

Creating Multiple Agents
---------------------

To create multiple agents, you'll need to:

1. Create agent identities
2. Initialize agents with different configurations
3. Register them with a communication hub

Here's an example:

.. code-block:: python

    import asyncio
    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, InteractionMode
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication import CommunicationHub
    
    async def setup_agents():
        # Create an agent registry and communication hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create identities for your agents
        assistant_identity = AgentIdentity.create_key_based()
        researcher_identity = AgentIdentity.create_key_based()
        coder_identity = AgentIdentity.create_key_based()
        
        # Create an assistant agent
        assistant_agent = AIAgent(
            agent_id="assistant-1",
            name="Assistant",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key="your-openai-api-key",
            identity=assistant_identity,
            interaction_modes=[
                InteractionMode.HUMAN_TO_AGENT,
                InteractionMode.AGENT_TO_AGENT
            ]
        )
        
        # Create a researcher agent
        researcher_agent = AIAgent(
            agent_id="researcher-1",
            name="Researcher",
            provider_type=ModelProvider.ANTHROPIC,
            model_name=ModelName.CLAUDE_3_7_SONNET,
            api_key="your-anthropic-api-key",
            identity=researcher_identity,
            interaction_modes=[
                InteractionMode.AGENT_TO_AGENT
            ]
        )
        
        # Create a coder agent
        coder_agent = AIAgent(
            agent_id="coder-1",
            name="Coder",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key="your-openai-api-key",
            identity=coder_identity,
            interaction_modes=[
                InteractionMode.AGENT_TO_AGENT
            ]
        )
        
        # Register the agents with the hub
        await hub.register_agent(assistant_agent)
        await hub.register_agent(researcher_agent)
        await hub.register_agent(coder_agent)
        
        return hub, [assistant_agent, researcher_agent, coder_agent]

Configuring Agent Communication
----------------------------

Once you have multiple agents, you need to configure how they communicate:

.. code-block:: python

    from agentconnect.core.message import Message
    from agentconnect.core.types import MessageType
    
    async def setup_communication(hub, agents):
        assistant, researcher, coder = agents
        
        # Set up message handlers
        async def assistant_handler(message):
            print(f"Assistant received: {message.content[:50]}...")
            # Process the message and potentially respond
        
        async def researcher_handler(message):
            print(f"Researcher received: {message.content[:50]}...")
            # Process the message and potentially respond
        
        async def coder_handler(message):
            print(f"Coder received: {message.content[:50]}...")
            # Process the message and potentially respond
        
        # Register the handlers with the hub
        hub.register_message_handler(assistant.agent_id, assistant_handler)
        hub.register_message_handler(researcher.agent_id, researcher_handler)
        hub.register_message_handler(coder.agent_id, coder_handler)

Orchestrating Multi-Agent Workflows
--------------------------------

To orchestrate workflows involving multiple agents:

.. code-block:: python

    async def run_workflow(hub, agents):
        assistant, researcher, coder = agents
        
        # User sends a request to the assistant
        user_identity = AgentIdentity.create_key_based()
        
        user_message = Message.create(
            sender_id="user-1",
            receiver_id=assistant.agent_id,
            content="I need to build a Python application that analyzes stock market data.",
            sender_identity=user_identity,
            message_type=MessageType.TEXT
        )
        
        # Assistant routes the request to the researcher for information gathering
        await hub.route_message(user_message)
        
        # In a real implementation, the assistant would process the message and then
        # decide to send a message to the researcher
        
        research_request = Message.create(
            sender_id=assistant.agent_id,
            receiver_id=researcher.agent_id,
            content="Find information about Python libraries for stock market analysis.",
            sender_identity=assistant.identity,
            message_type=MessageType.TEXT
        )
        
        await hub.route_message(research_request)
        
        # The researcher would process and respond, then the assistant might
        # send a request to the coder
        
        coding_request = Message.create(
            sender_id=assistant.agent_id,
            receiver_id=coder.agent_id,
            content="Create a Python script that uses pandas and yfinance to analyze stock data.",
            sender_identity=assistant.identity,
            message_type=MessageType.TEXT
        )
        
        await hub.route_message(coding_request)
        
        # In a real implementation, you would have proper message handling and
        # response processing

Complete Example
-------------

Here's a complete example that sets up multiple agents and runs a simple workflow:

.. code-block:: python

    import asyncio
    import logging
    
    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, MessageType, InteractionMode
    from agentconnect.core.message import Message
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication import CommunicationHub
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    async def main():
        # Create an agent registry and communication hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create identities for your agents
        assistant_identity = AgentIdentity.create_key_based()
        researcher_identity = AgentIdentity.create_key_based()
        user_identity = AgentIdentity.create_key_based()
        
        # Create an assistant agent
        assistant_agent = AIAgent(
            agent_id="assistant-1",
            name="Assistant",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key="your-openai-api-key",
            identity=assistant_identity
        )
        
        # Create a researcher agent
        researcher_agent = AIAgent(
            agent_id="researcher-1",
            name="Researcher",
            provider_type=ModelProvider.ANTHROPIC,
            model_name=ModelName.CLAUDE_3_7_SONNET,
            api_key="your-anthropic-api-key",
            identity=researcher_identity
        )
        
        # Register the agents with the hub
        await hub.register_agent(assistant_agent)
        await hub.register_agent(researcher_agent)
        
        # Set up message handlers
        async def assistant_handler(message):
            logger.info(f"Assistant received: {message.content[:50]}...")
            
            if message.sender_id == "user-1":
                # Forward to researcher for more information
                research_request = Message.create(
                    sender_id=assistant_agent.agent_id,
                    receiver_id=researcher_agent.agent_id,
                    content=f"Research this topic: {message.content}",
                    sender_identity=assistant_agent.identity,
                    message_type=MessageType.TEXT
                )
                await hub.route_message(research_request)
            
            elif message.sender_id == researcher_agent.agent_id:
                # Process research results and respond to user
                user_response = Message.create(
                    sender_id=assistant_agent.agent_id,
                    receiver_id="user-1",
                    content=f"Based on research, here's what I found: {message.content}",
                    sender_identity=assistant_agent.identity,
                    message_type=MessageType.RESPONSE
                )
                await hub.route_message(user_response)
        
        async def researcher_handler(message):
            logger.info(f"Researcher received: {message.content[:50]}...")
            
            # Simulate research process
            research_result = f"Research results for: {message.content}"
            
            # Send results back to assistant
            response = Message.create(
                sender_id=researcher_agent.agent_id,
                receiver_id=message.sender_id,
                content=research_result,
                sender_identity=researcher_agent.identity,
                message_type=MessageType.RESPONSE
            )
            await hub.route_message(response)
        
        async def user_handler(message):
            logger.info(f"User received: {message.content[:50]}...")
            # In a real application, you would display this to the user
        
        # Register the handlers with the hub
        hub.register_message_handler(assistant_agent.agent_id, assistant_handler)
        hub.register_message_handler(researcher_agent.agent_id, researcher_handler)
        hub.register_message_handler("user-1", user_handler)
        
        # Start the workflow with a user message
        user_message = Message.create(
            sender_id="user-1",
            receiver_id=assistant_agent.agent_id,
            content="Tell me about quantum computing applications.",
            sender_identity=user_identity,
            message_type=MessageType.TEXT
        )
        
        # Send the message through the hub
        logger.info(f"User sending message: {user_message.content}")
        await hub.route_message(user_message)
        
        # In a real application, you would have a proper event loop
        # For this example, we'll just wait a short time for the workflow to complete
        await asyncio.sleep(5)
        
        logger.info("Multi-agent workflow completed")
    
    # Run the async function
    if __name__ == "__main__":
        asyncio.run(main()) 