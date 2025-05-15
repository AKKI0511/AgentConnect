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

AgentConnect now recommends configuring your AI agent using an `AgentProfile`. This provides a single, comprehensive, and structured way to define all the agent's characteristics, making your agent easier to discover and manage. While you can still use individual parameters (like `name` or `capabilities`) for backward compatibility, using `AgentProfile` is the preferred and future-proof approach.

Here's how to define a simple `AgentProfile` and use it to initialize your AI agent:

.. code-block:: python

    from agentconnect.core.types import AgentProfile, Capability, AgentType, ModelProvider, ModelName, AgentIdentity, InteractionMode
    
    # Example AgentProfile
    my_agent_profile = AgentProfile(
        agent_id="my_chat_agent_01",
        agent_type=AgentType.AI,
        name="ChattyHelper",
        summary="A simple AI agent that can greet and echo messages.",
        capabilities=[
            Capability(
                name="greet_user",
                description="Responds to user greetings."
            ),
            Capability(
                name="echo_message",
                description="Repeats any message sent to it."
            )
        ],
        # You can also add other fields like:
        # description="A more detailed explanation of what this agent does and its purpose.",
        # version="1.0.0",
        # tags=["example", "chatbot", "beginner"]
    )

    # Create an AI agent using the profile (recommended)
    ai_assistant = AIAgent(
        agent_id=my_agent_profile.agent_id,  # Usually matches profile.agent_id
        identity=ai_identity,                # Identity created earlier
        provider_type=ModelProvider.OPENAI,  # Choose your provider
        model_name=ModelName.GPT4O_MINI,     # Choose your model
        api_key=os.getenv("OPENAI_API_KEY"),# API key from .env
        profile=my_agent_profile,            # Pass the profile here
        # ... other AIAgent-specific parameters if needed
    )

**Why use AgentProfile?**

- `AgentProfile` is the new recommended method for configuring an agent because it provides a single, comprehensive, and structured way to define all its characteristics.
- While individual parameters (like a standalone `name` or `capabilities` list) might still function for simpler cases or backward compatibility, `AgentProfile` is the preferred approach for its richness and clarity.
- This detailed `AgentProfile` is what gets registered with the `AgentRegistry` and is essential for effective agent discovery, especially with the enhanced semantic search features.
- The `AIAgent` constructor will still require other fundamental parameters like `identity`, `provider_type`, `model_name`, and `api_key`, in addition to the `profile`.

**Note:** Fields such as `name`, `capabilities`, and more are now part of the `AgentProfile` object, not direct arguments to `AIAgent`.

Configuring a Human Agent
-----------------------

For interactive testing, let's create a human agent that can chat with our AI:

.. code-block:: python

    # Create a human agent for interaction
    human = HumanAgent(
        agent_id="human1",              # Unique identifier
        name="User",                    # Human-readable name
        identity=human_identity,        # Identity created earlier
        organization="org1",         # Optional organization grouping
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
        ModelProvider, 
        AgentProfile, 
        AgentType
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
            organization="org1"
        )
        
        # Define the AgentProfile for the AI agent
        my_agent_profile = AgentProfile(
            agent_id="my_chat_agent_01",
            agent_type=AgentType.AI,
            name="ChattyHelper",
            summary="A simple AI agent that can greet and echo messages.",
            capabilities=[
                Capability(
                    name="greet_user",
                    description="Responds to user greetings."
                ),
                Capability(
                    name="echo_message",
                    description="Repeats any message sent to it."
                )
            ],
            # Optionally add more fields like description, version, tags, etc.
        )
        
        # Create the AI agent using the profile
        ai_assistant = AIAgent(
            agent_id=my_agent_profile.agent_id,
            identity=ai_identity,
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O_MINI,
            api_key=os.getenv("OPENAI_API_KEY"),
            profile=my_agent_profile,
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