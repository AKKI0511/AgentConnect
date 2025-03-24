# Quickstart

This guide will help you get started with AgentConnect, a framework that enables independent AI agents to discover, communicate, and collaborate with each other through capability-based discovery.

## What is AgentConnect?

AgentConnect allows you to:

- Create independent AI agents with specific capabilities
- Enable secure communication between agents with cryptographic verification
- Discover agents based on their capabilities rather than pre-defined connections
- Build systems where each agent can operate autonomously while collaborating with others
- Develop multi-agent workflows for complex tasks

## Basic Usage: Human-AI Interaction

Let's start with a simple example of a human user interacting with an AI assistant:

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.agents import AIAgent, HumanAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    ModelProvider,
    ModelName,
    InteractionMode,
    AgentIdentity,
    Capability,
)
from agentconnect.core.message import Message

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create secure agent identities with cryptographic keys
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()
    
    # Create a human agent
    human = HumanAgent(
        agent_id="human1",
        name="User",
        identity=human_identity,
        organization_id="org1"
    )
    
    # Define AI agent capabilities (what this agent can do)
    ai_capabilities = [
        Capability(
            name="conversation",
            description="General conversation and assistance",
            input_schema={"query": "string"},
            output_schema={"response": "string"},
        )
    ]
    
    # Create an AI assistant with the defined capabilities
    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=ModelProvider.GROQ,  # Choose your provider
        model_name=ModelName.LLAMA3_70B,   # Choose your model
        api_key=os.getenv("GROQ_API_KEY"),
        identity=ai_identity,
        capabilities=ai_capabilities,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",
        organization_id="org2",
    )
    
    # Register agents with the hub for discovery
    await hub.register_agent(human)
    await hub.register_agent(ai_assistant)
    
    # Start AI processing loop
    ai_task = asyncio.create_task(ai_assistant.run())
    
    # Start interactive session
    await human.start_interaction(ai_assistant)
    
    # Cleanup
    ai_assistant.is_running = False
    await ai_task
    await hub.unregister_agent(human.agent_id)
    await hub.unregister_agent(ai_assistant.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
```

## Agent Collaboration

You can create specialized agents that collaborate on tasks without human intervention:

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.agents import AIAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    ModelProvider,
    ModelName,
    InteractionMode,
    AgentIdentity,
    Capability,
)

async def message_handler(message: Message) -> None:
    """Track all messages passing through the hub"""
    print(f"Message routed: {message.sender_id} → {message.receiver_id}")
    print(f"Content: {message.content[:50]}...")

async def run_multi_agent_demo():
    load_dotenv()
    
    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Add a global message handler to track all communication
    hub.add_global_handler(message_handler)
    
    # Create agent identities
    agent1_identity = AgentIdentity.create_key_based()
    agent2_identity = AgentIdentity.create_key_based()
    
    # Define specialized capabilities
    data_processing_capability = Capability(
        name="data_processing",
        description="Process and transform raw data into structured formats",
        input_schema={"data": "Any raw data format"},
        output_schema={"processed_data": "Structured data format"},
    )
    
    business_analysis_capability = Capability(
        name="business_analysis",
        description="Analyze business performance and metrics",
        input_schema={"business_data": "Business performance metrics"},
        output_schema={"business_insights": "Business performance analysis"},
    )
    
    # Create specialized agents
    data_processor = AIAgent(
        agent_id="processor1",
        name="DataProcessor",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=agent1_identity,
        capabilities=[data_processing_capability],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="detail-oriented data analyst",
    )
    
    business_analyst = AIAgent(
        agent_id="analyst1",
        name="BusinessAnalyst",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=agent2_identity,
        capabilities=[business_analysis_capability],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="strategic business analyst",
    )
    
    # Register agents
    await hub.register_agent(data_processor)
    await hub.register_agent(business_analyst)
    
    # Start agent processing loops
    tasks = [
        asyncio.create_task(data_processor.run()),
        asyncio.create_task(business_analyst.run())
    ]
    
    # Initiate communication between agents
    await data_processor.send_message(
        receiver_id=business_analyst.agent_id,
        content="I have processed the sales data for Q2. Revenue is up 15% compared to Q1. Would you analyze these trends?",
    )
    
    # Let agents communicate for a while
    await asyncio.sleep(60)
    
    # Cleanup
    for agent in [data_processor, business_analyst]:
        agent.is_running = False
    
    for task in tasks:
        await task
    
    await hub.unregister_agent(data_processor.agent_id)
    await hub.unregister_agent(business_analyst.agent_id)

if __name__ == "__main__":
    asyncio.run(run_multi_agent_demo())
```

## Message Handling and Event Tracking

You can add message handlers to track and respond to agent communications:

```python
from agentconnect.core.message import Message
from agentconnect.core.types import MessageType

# Handler for a specific agent
async def agent_message_handler(message: Message) -> None:
    print(f"Agent received: {message.content}")
    # Log, analyze, or take action based on messages

# Add handlers to the hub
hub.add_message_handler("agent_id", agent_message_handler)

# Add a global handler to monitor all messages
async def global_message_tracker(message: Message) -> None:
    if message.message_type == MessageType.REQUEST_COLLABORATION:
        print(f"Collaboration request: {message.sender_id} → {message.receiver_id}")
    elif message.message_type == MessageType.COLLABORATION_RESPONSE:
        print(f"Collaboration response received from {message.sender_id}")

hub.add_global_handler(global_message_tracker)
```

## Capability-Based Discovery

Agents can discover and collaborate with other agents based on capabilities:

```python
# Find agents with specific capabilities
matching_agents = await registry.find_agents_by_capability(
    capability_name="data_analysis"
)

if matching_agents:
    # Request collaboration from the first matching agent
    analysis_result = await hub.send_collaboration_request(
        sender_id=requester.agent_id,
        receiver_id=matching_agents[0].agent_id,
        task_description="Analyze this dataset: [1, 2, 3, 4, 5]"
    )
```

## Key Components

### Agents

- `AIAgent`: AI-powered agent with specific capabilities that can operate independently
- `HumanAgent`: Interface for human users to participate in the agent network

### Communication

- `CommunicationHub`: Message routing system that enables agent discovery and interaction
- `AgentRegistry`: Registry for capability-based agent discovery

### Protocols

- `SimpleAgentProtocol`: Ensures secure agent-to-agent communication
- `CollaborationProtocol`: Enables capability discovery and task delegation

### Core Types

- `AgentIdentity`: Secure identity with cryptographic verification
- `Capability`: Structured representation of what an agent can do
- `ModelProvider`: Supported AI providers (OpenAI, Anthropic, Groq, Google, etc.)
- `ModelName`: Available models for each provider
- `MessageType`: Different types of messages (TEXT, REQUEST_COLLABORATION, etc.)

## Next Steps

- Explore the [Examples](https://github.com/AKKI0511/AgentConnect/tree/main/examples) directory for more detailed implementations
- Check out the [API Reference](https://AKKI0511.github.io/AgentConnect/api/) for detailed information
- Learn about [Advanced Features](https://AKKI0511.github.io/AgentConnect/advanced/) for customizing agent behavior 