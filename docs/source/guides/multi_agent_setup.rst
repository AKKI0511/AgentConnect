Multi-Agent Setup Guide
======================

.. _multi_agent_setup:

This guide explains how to set up multiple agents that can collaborate, discover each other based on capabilities, and work together to solve complex problems.

Introduction
-----------

In AgentConnect, multi-agent systems consist of independent agents—each with their own specialized capabilities—working together through standardized communication. The framework handles agent discovery and message routing automatically, allowing you to focus on defining the agents and their skills.

The core value of multi-agent systems comes from:

- **Specialization**: Agents can focus on specific tasks they excel at
- **Modularity**: New capabilities can be added by introducing new agents
- **Scalability**: Systems can grow organically as needs evolve
- **Separation of concerns**: Each agent manages its own internal logic

Core Principles of Multi-Agent Setup
-----------------------------------

The key to enabling collaboration between agents lies in three fundamental concepts:

1. **Capabilities & Profiles**: Clearly defined agent profiles with specific capabilities they can provide
2. **Registry**: A directory for capability-based discovery
3. **Communication Hub**: A message router connecting agents based on registry lookups

Let's explore each of these principles:

Agent Profiles & Capabilities: The Foundation of Collaboration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each agent declares its capabilities—the services it can provide to other agents—as part of its ``AgentProfile``. These capability definitions include:

- A unique name
- A clear description
- Input and output schemas (optional)

For example:

.. code-block:: python

    from agentconnect.core.types import Capability, AgentProfile, AgentType, Skill
    
    # Define a summarization capability
    summarization_capability = Capability(
        name="text_summarization",
        description="Summarizes text content into concise form",
        input_schema={"text": "string", "max_length": "integer"},
        output_schema={"summary": "string"}
    )
    
    # Define a data analysis capability
    analysis_capability = Capability(
        name="data_analysis",
        description="Analyzes data and provides insights",
        input_schema={"data": "string"},
        output_schema={"analysis": "string"}
    )
    
    # Create an AgentProfile for a summarizer agent
    summarizer_profile = AgentProfile(
        agent_id="summarizer_agent",
        agent_type=AgentType.AI,
        name="Text Summarizer",
        summary="Specializes in creating concise summaries of long texts",
        description="This agent can summarize articles, papers, and long texts into shorter versions while preserving key information.",
        capabilities=[summarization_capability],
        skills=[Skill(name="text_compression", description="Ability to compress text while retaining meaning")],
        tags=["summarization", "text processing", "content"]
    )
    
    # Create an AgentProfile for an analyzer agent
    analyzer_profile = AgentProfile(
        agent_id="data_analyzer",
        agent_type=AgentType.AI,
        name="Data Analyzer",
        summary="Specializes in analyzing datasets and extracting insights",
        description="This agent can analyze different types of data and provide statistical insights and visualizations.",
        capabilities=[analysis_capability],
        skills=[Skill(name="statistical_analysis", description="Ability to analyze numerical data")],
        tags=["analysis", "data", "insights"]
    )

When you create an agent with these profiles, you're providing a rich description of what services the agent can provide to others in the system, making discovery and collaboration more effective.

Registry: The Agent Directory
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``AgentRegistry`` serves as a dynamic directory of all available agents and their profiles. When an agent needs a specific capability, the registry provides the means to find agents that offer it.

.. code-block:: python

    from agentconnect.core.registry import AgentRegistry
    
    # Create the registry
    registry = AgentRegistry()

Communication Hub: Message Routing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``CommunicationHub`` handles message routing between agents, allowing them to exchange information regardless of where they're located:

.. code-block:: python

    from agentconnect.communication import CommunicationHub
    
    # Create the hub with reference to the registry
    hub = CommunicationHub(registry)

Step-by-Step Guide to Setup
--------------------------

Now let's walk through the steps to create a multi-agent system:

Step 1: Define Agent Roles & Profiles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, plan what agents you need and what profiles each should have. For example:

- **Orchestrator Agent**: Coordinates workflows, interacts with users
- **Summarizer Agent**: Specializes in condensing text into summaries

For each agent, define a clear, comprehensive AgentProfile with well-described capabilities that other agents can discover and use.

Step 2: Create Agent Identities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each agent needs a secure identity for authentication and message signing:

.. code-block:: python

    from agentconnect.core.types import AgentIdentity
    
    # Create identities for each agent
    orchestrator_identity = AgentIdentity.create_key_based()
    summarizer_identity = AgentIdentity.create_key_based()
    analyst_identity = AgentIdentity.create_key_based()

Step 3: Instantiate Agents
~~~~~~~~~~~~~~~~~~~~~~~

Create each agent with its unique identity, profile, and provider configuration:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentProfile, AgentType, Capability, Skill, InteractionMode
    
    # Create an orchestrator profile
    orchestrator_profile = AgentProfile(
        agent_id="orchestrator",
        agent_type=AgentType.AI,
        name="Orchestrator",
        summary="Coordinates tasks and delegates to specialized agents",
        description="This agent manages complex workflows by breaking them down and delegating subtasks to specialized agents.",
        capabilities=[
            Capability(
                name="task_management",
                description="Manages and coordinates complex tasks",
                input_schema={"task": "string"},
                output_schema={"result": "string"}
            )
        ],
        skills=[
            Skill(name="task_delegation", description="Ability to delegate tasks to appropriate specialized agents")
        ],
        tags=["orchestration", "coordination", "workflow"]
    )
    
    # Create a summarizer profile
    summarizer_profile = AgentProfile(
        agent_id="summarizer",
        agent_type=AgentType.AI,
        name="Summarizer",
        summary="Creates concise summaries of text content",
        description="This agent specializes in condensing long text into shorter, more digestible summaries while preserving key information.",
        capabilities=[
            Capability(
                name="text_summarization",
                description="Summarizes text into concise form",
                input_schema={"text": "string", "max_length": "integer"},
                output_schema={"summary": "string"}
            )
        ],
        skills=[
            Skill(name="text_comprehension", description="Understanding and extracting key information from text")
        ],
        tags=["summarization", "content", "text"]
    )
    
    # Create an orchestrator agent using its profile
    orchestrator = AIAgent(
        agent_id=orchestrator_profile.agent_id,
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=orchestrator_identity,
        profile=orchestrator_profile,
        personality="I coordinate complex tasks by working with specialized agents.",
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT]
    )
    
    # Create a summarizer agent using its profile
    summarizer = AIAgent(
        agent_id=summarizer_profile.agent_id,
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=summarizer_identity,
        profile=summarizer_profile,
        personality="I specialize in creating concise summaries of text content.",
        interaction_modes=[InteractionMode.AGENT_TO_AGENT]
    )

.. note:: 
    Using the ``AgentProfile`` approach provides richer metadata for agent discovery, improves semantic search within the registry, and makes collaboration more effective. The profile contains all the external-facing information about what an agent is and can do, while the ``AIAgent`` constructor handles how it operates (provider, model, personality, etc.).

Notice how each agent has a unique profile with different capabilities, even though they may use the same underlying AI model.

Step 4: Initialize Hub & Registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create the registry and hub that will connect your agents:

.. code-block:: python

    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

Step 5: Register All Agents
~~~~~~~~~~~~~~~~~~~~~~~~

Register each agent with the hub to make them discoverable:

.. code-block:: python

    # Register all agents
    await hub.register_agent(orchestrator)
    await hub.register_agent(summarizer)

This step is crucial—only registered agents can be discovered by others based on their capabilities.

Step 6: Start Agent Run Loops
~~~~~~~~~~~~~~~~~~~~~~~~~~

Start each agent's processing loop so they can receive and handle messages:

.. code-block:: python

    # Start all agent loops
    orchestrator_task = asyncio.create_task(orchestrator.run())
    summarizer_task = asyncio.create_task(summarizer.run())

Each agent now runs independently, listening for messages and processing them based on their internal logic.

Initiating Collaboration
----------------------

There are several ways agents can collaborate within the AgentConnect framework:

**Direct Agent-to-Agent Communication**

The simplest approach is when one agent explicitly sends a message to another:

.. code-block:: python

    # Orchestrator directly messages the summarizer
    await orchestrator.send_message(
        receiver_id=summarizer.agent_id,
        content="Please summarize the following text: 'AgentConnect enables decentralized agent collaboration...'",
        message_type=MessageType.TEXT
    )

**Human-Initiated Workflows**

Often, a human user initiates the workflow by interacting with a primary agent:

.. code-block:: python

    # Create and register a human agent
    human = HumanAgent(
        agent_id="human",
        name="User",
        identity=human_identity
    )
    await hub.register_agent(human)
    
    # Start human interaction with the primary agent
    await human.start_interaction(orchestrator)

The human's messages trigger the orchestrator, which then coordinates with other agents as needed to fulfill requests.

**Capability-Based Discovery and Collaboration**

In more sophisticated workflows, agents use built-in collaboration tools to discover each other and work together. These tools abstract the complexity of registry lookups and message exchange.

For example, an agent might use:

- ``search_for_agents`` to find other agents with specific capabilities
- ``send_collaboration_request`` to delegate tasks and manage responses

These built-in tools enable truly dynamic collaboration where agents discover and work with each other based on capabilities rather than hardcoded agent IDs. For a detailed exploration of these collaboration patterns, see the :doc:`collaborative_workflows` guide.

Simplified Example: Task Delegation
---------------------------------

Here's a complete example demonstrating a basic multi-agent setup with task delegation:

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
        MessageType,
        AgentProfile,
        AgentType,
        Skill
    )
    
    async def main():
        # Load environment variables
        load_dotenv()
        
        # Create the registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create agent identities
        orchestrator_identity = AgentIdentity.create_key_based()
        summarizer_identity = AgentIdentity.create_key_based()
        human_identity = AgentIdentity.create_key_based()
        
        # Create agent profiles
        orchestrator_profile = AgentProfile(
            agent_id="orchestrator",
            agent_type=AgentType.AI,
            name="Orchestrator",
            summary="Coordinates tasks and delegates to specialized agents",
            description="This agent manages complex workflows by breaking them down and delegating subtasks to specialized agents.",
            capabilities=[
                Capability(
                    name="task_coordination",
                    description="Coordinates tasks and delegates to specialized agents",
                    input_schema={"request": "string"},
                    output_schema={"result": "string"}
                )
            ],
            skills=[
                Skill(name="workflow_management", description="Managing complex workflows")
            ],
            tags=["orchestration", "coordination", "workflow"]
        )
        
        summarizer_profile = AgentProfile(
            agent_id="summarizer",
            agent_type=AgentType.AI,
            name="Summarizer",
            summary="Creates concise summaries of text content",
            description="This agent specializes in condensing long text into shorter, more digestible summaries while preserving key information.",
            capabilities=[
                Capability(
                    name="text_summarization",
                    description="Summarizes text into concise form",
                    input_schema={"text": "string", "max_length": "integer"},
                    output_schema={"summary": "string"}
                )
            ],
            skills=[
                Skill(name="text_comprehension", description="Understanding and extracting key information from text")
            ],
            tags=["summarization", "content", "text"]
        )
        
        # Create agents using their profiles
        orchestrator = AIAgent(
            agent_id=orchestrator_profile.agent_id,
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
            identity=orchestrator_identity,
            profile=orchestrator_profile,
            personality="I'm a coordinator who delegates tasks to specialized agents.",
        )
        
        summarizer = AIAgent(
            agent_id=summarizer_profile.agent_id,
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
            identity=summarizer_identity,
            profile=summarizer_profile,
            personality="I specialize in creating concise summaries of text content.",
            interaction_modes=[InteractionMode.AGENT_TO_AGENT]
        )
        
        # Create a human agent
        human = HumanAgent(
            agent_id="human",
            name="User",
            identity=human_identity,
        )
        
        # Register all agents
        await hub.register_agent(orchestrator)
        await hub.register_agent(summarizer)
        await hub.register_agent(human)
        
        # Start agent processing loops
        orchestrator_task = asyncio.create_task(orchestrator.run())
        summarizer_task = asyncio.create_task(summarizer.run())
        
        try:
            # Simulate a direct collaboration
            print("Demonstrating direct collaboration...")
            
            # Orchestrator sends a task to the summarizer
            # Note: In a more dynamic scenario, the orchestrator might first use
            # the search_for_agents tool to find agents with summarization capabilities
            await orchestrator.send_message(
                receiver_id=summarizer.agent_id,
                content="Please summarize the following text: 'AgentConnect is a framework for building decentralized multi-agent systems. It provides tools for agent identity, messaging, and capability discovery. Agents can find and collaborate with each other based on their capabilities without centralized control.'",
                message_type=MessageType.TEXT
            )
            
            # In a real system, the summarizer would process this and respond
            # The orchestrator would receive the response via its run() loop
            
            # Wait a moment to let the message processing occur
            await asyncio.sleep(5)
            
            print("\nNow starting human interaction with orchestrator...")
            # Start human interaction for a more natural workflow
            await human.start_interaction(orchestrator)
            
        finally:
            # Cleanup
            print("Shutting down agents...")
            await orchestrator.stop()
            await summarizer.stop()
            await hub.unregister_agent(orchestrator.agent_id)
            await hub.unregister_agent(summarizer.agent_id)
            await hub.unregister_agent(human.agent_id)
            print("Done.")
    
    if __name__ == "__main__":
        asyncio.run(main())

When you run this example:

1. Two AI agents are created with different profiles and capabilities
2. Both agents are registered with the hub
3. Both agents start their processing loops
4. The orchestrator sends a summarization task to the summarizer
5. The human user can then interact with the orchestrator to trigger more complex workflows

Monitoring Interactions
---------------------

To understand what's happening in your multi-agent system, AgentConnect provides built-in monitoring:

.. code-block:: python

    from agentconnect.utils.callbacks import ToolTracerCallbackHandler
    
    # Add this when creating an agent
    orchestrator = AIAgent(
        # ... other parameters ...
        external_callbacks=[
            ToolTracerCallbackHandler(
                agent_id="orchestrator",
                print_tool_activity=True,
                print_reasoning_steps=True
            )
        ]
    )

The ``ToolTracerCallbackHandler`` provides detailed, color-coded output showing:

- Messages sent and received
- Tool usage and function calls
- Agent reasoning steps

For more advanced monitoring using LangSmith, see the :doc:`event_monitoring` guide.

Conclusion & Next Steps
---------------------

You've now learned the fundamental principles of setting up multiple agents for collaboration in AgentConnect:

1. Define comprehensive agent profiles for each agent
2. Register all agents with the hub
3. Start each agent's processing loop
4. Initiate collaboration through direct messages or human interaction

This setup enables a flexible, extensible multi-agent system where agents can discover and communicate with each other based on their profiles and capabilities.

To build on this foundation:

- Learn how to design more complex collaborative workflows in :doc:`collaborative_workflows`
- Discover how to equip agents with external tools in :doc:`external_tools`
- Explore options for payment-enabled agents in :doc:`agent_payment`
- Learn more about configuring individual agents in :doc:`agent_configuration`
