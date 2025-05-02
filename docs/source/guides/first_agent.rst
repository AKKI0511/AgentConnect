Your First Agent
===============

.. _first_agent:

This guide will walk you through creating and running your first AI agent with AgentConnect. By the end, you'll have a functioning AI agent that can communicate through the AgentConnect framework.

Prerequisites
------------

Before starting, make sure you have:

- Python 3.11 or higher installed
- Cloned the AgentConnect repository
- Installed dependencies with Poetry
- Set up your API keys in a `.env` file

If you haven't completed these steps, refer to the main :doc:`../installation` or the :doc:`../quickstart`.

Setup & Imports
--------------

First, let's create a new Python file (e.g., ``my_first_agent.py``) and add the necessary imports:

.. code-block:: python

    import asyncio
    import os
    from dotenv import load_dotenv
    
    from agentconnect.agents import AIAgent, HumanAgent
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.core.types import (
        AgentIdentity, 
        Capability, 
        InteractionMode, 
        ModelName, 
        ModelProvider
    )

Loading Environment Variables
---------------------------

Next, we'll load environment variables to access our API keys:

.. code-block:: python

    async def main():
        # Load variables from .env file
        load_dotenv()
        
        # Now we can access API keys like os.getenv("OPENAI_API_KEY")

Initializing Core Components
--------------------------

Let's initialize the two fundamental components of AgentConnect:

.. code-block:: python

    # Create the Agent Registry - the "phone book" of agents
    registry = AgentRegistry()
    
    # Create the Communication Hub - routes messages between agents
    hub = CommunicationHub(registry)

Creating Agent Identities
-----------------------

Each agent needs a secure identity for authentication and messaging:

.. code-block:: python

    # Create identities with cryptographic keys
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()

Configuring the AI Agent
----------------------

Now we'll create our AI agent with specific capabilities:

.. code-block:: python

    # Create an AI agent with a specific provider/model
    ai_assistant = AIAgent(
        agent_id="ai1",                          # Unique identifier
        name="Assistant",                        # Human-readable name
        provider_type=ModelProvider.OPENAI,      # Choose your provider
        model_name=ModelName.GPT4O,              # Choose your model
        api_key=os.getenv("OPENAI_API_KEY"),     # API key from .env
        identity=ai_identity,                    # Identity created earlier
        capabilities=[
            Capability(
                name="conversation",
                description="General conversation and assistance",
                input_schema={"query": "string"},
                output_schema={"response": "string"},
            )
        ],
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",   # Personality traits
        organization_id="org1",                   # Optional organization grouping
    )

The key parameters you can adjust:

- **provider_type**: Choose from ``ModelProvider.OPENAI``, ``ModelProvider.ANTHROPIC``, ``ModelProvider.GOOGLE``, etc.
- **model_name**: Select from ``ModelName.GPT4O``, ``ModelName.O1``, ``ModelName.CLAUDE_3_7_SONNET``, etc.
- **capabilities**: Define what your agent can do (these are discoverable by other agents)
- **personality**: Adjust how your agent responds

Configuring a Human Agent
-----------------------

For interactive testing, let's create a human agent that can chat with our AI:

.. code-block:: python

    # Create a human agent for interaction
    human = HumanAgent(
        agent_id="human1",              # Unique identifier
        name="User",                    # Human-readable name
        identity=human_identity,        # Identity created earlier
        organization_id="org1",         # Optional organization grouping
    )

Registering Agents
----------------

To make our agents discoverable, we register them with the hub:

.. code-block:: python

    # Register both agents with the hub
    await hub.register_agent(human)
    await hub.register_agent(ai_assistant)

Running the Agent
--------------

Now we'll start the agent's processing loop:

.. code-block:: python

    # Start the AI agent's processing loop as a background task
    ai_task = asyncio.create_task(ai_assistant.run())

Initiating Interaction
-------------------

With everything set up, we can start chatting with our AI agent:

.. code-block:: python

    # Start interactive terminal chat session
    await human.start_interaction(ai_assistant)

Cleanup
------

Finally, let's clean up resources when we're done:

.. code-block:: python

    # Stop the AI agent
    await ai_assistant.stop()
    
    # Unregister agents
    await hub.unregister_agent(human.agent_id)
    await hub.unregister_agent(ai_assistant.agent_id)

Complete Example
--------------

Here's the complete script:

.. code-block:: python

    import asyncio
    import os
    from dotenv import load_dotenv
    
    from agentconnect.agents import AIAgent, HumanAgent
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.core.types import (
        AgentIdentity, 
        Capability, 
        InteractionMode, 
        ModelName, 
        ModelProvider
    )
    
    async def main():
        # Load environment variables
        load_dotenv()
        
        # Initialize registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create agent identities
        human_identity = AgentIdentity.create_key_based()
        ai_identity = AgentIdentity.create_key_based()
        
        # Create a human agent
        human = HumanAgent(
            agent_id="human1",
            name="User",
            identity=human_identity,
            organization_id="org1"
        )
        
        # Create an AI agent
        ai_assistant = AIAgent(
            agent_id="ai1",
            name="Assistant",
            provider_type=ModelProvider.OPENAI,  # Or ModelProvider.GROQ, etc.
            model_name=ModelName.GPT4O,          # Choose your model
            api_key=os.getenv("OPENAI_API_KEY"),
            identity=ai_identity,
            capabilities=[Capability(
                name="conversation",
                description="General conversation and assistance",
                input_schema={"query": "string"},
                output_schema={"response": "string"},
            )],
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
            personality="helpful and professional",
            organization_id="org1",
        )
        
        # Register agents with the hub
        await hub.register_agent(human)
        await hub.register_agent(ai_assistant)
        
        # Start AI processing loop
        ai_task = asyncio.create_task(ai_assistant.run())
        
        # Start interactive session
        await human.start_interaction(ai_assistant)
        
        # Cleanup
        await ai_assistant.stop()
        await hub.unregister_agent(human.agent_id)
        await hub.unregister_agent(ai_assistant.agent_id)
    
    if __name__ == "__main__":
        asyncio.run(main())

Running the Script
----------------

To run your script:

.. code-block:: shell

    python my_first_agent.py

You'll see a terminal prompt where you can interact with your AI agent. Type messages and receive responses. To exit the conversation, type "exit", "quit", or "bye".

Next Steps
---------

Now that you've created your first agent, you're ready to explore more complex scenarios:

- Try changing the agent's capabilities or personality
- Experiment with different model providers
- Learn how to set up multiple agents in the :doc:`multi_agent_setup` guide 
- Explore how to integrate human agents using :doc:`human_in_the_loop` 