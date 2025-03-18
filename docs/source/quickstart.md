# Quickstart

This guide will help you get started with AgentConnect quickly.

## Basic Usage

Here's a simple example of how to create and connect AI agents:

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

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create secure agent identities
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
    ai_capabilities = [
        Capability(
            name="conversation",
            description="General conversation and assistance",
            input_schema={"query": "string"},
            output_schema={"response": "string"},
        )
    ]
    
    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=ModelProvider.GROQ,  # Or any other provider
        model_name=ModelName.LLAMA3_70B,   # Or any other model
        api_key=os.getenv("GROQ_API_KEY"),
        identity=ai_identity,
        capabilities=ai_capabilities,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",
        organization_id="org2",
    )
    
    # Register agents
    await hub.register_agent(human)
    await hub.register_agent(ai_assistant)
    
    # Start AI processing
    ai_task = asyncio.create_task(ai_assistant.run())
    
    # Start interaction
    await human.start_interaction(ai_assistant)
    
    # Cleanup
    ai_assistant.is_running = False
    await ai_task
    await hub.unregister_agent(human.agent_id)
    await hub.unregister_agent(ai_assistant.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
```

## Multi-Agent Systems

AgentConnect supports creating multi-agent systems where agents can collaborate autonomously:

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

async def run_multi_agent_demo():
    load_dotenv()
    
    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
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

## Key Components

### Agents

- `AIAgent`: AI-powered agent that can process messages and generate responses
- `HumanAgent`: Interface for human users to interact with AI agents

### Communication

- `CommunicationHub`: Central component for message routing and agent communication
- `AgentRegistry`: Registry for agent discovery and capability matching

### Core Types

- `AgentIdentity`: Secure identity with cryptographic verification
- `Capability`: Structured representation of agent capabilities
- `ModelProvider`: Supported AI providers (OpenAI, Anthropic, Groq, Google)
- `ModelName`: Available models for each provider

## Next Steps

- Check out the [Examples](https://github.com/AKKI0511/AgentConnect/tree/main/examples) directory for more detailed examples
- Explore the [API Reference](https://akki0511.github.io/AgentConnect/api/) for detailed information about available classes and methods
- Learn about [Advanced Features](https://akki0511.github.io/AgentConnect/advanced/) for customizing agent behavior 