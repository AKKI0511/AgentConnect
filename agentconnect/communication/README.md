# Communication Module

The communication module provides the infrastructure for peer-to-peer agent communication in the AgentConnect framework. It handles message routing and agent discovery without dictating agent behavior.

## Structure

```
communication/
├── __init__.py         # Package initialization and API exports
├── hub.py              # CommunicationHub implementation
└── README.md           # This file
```

## Key Components

### CommunicationHub

The `CommunicationHub` is a message routing system that:
- Facilitates agent discovery through registration
- Routes messages between independent agents
- Ensures secure message delivery
- Tracks message history for auditability

**Important**: The hub does NOT control agent behavior. It simply enables discovery and communication between independent agents, each of which makes its own decisions about how to respond to messages.

```python
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry

# Create a message routing hub
registry = AgentRegistry()
hub = CommunicationHub(registry)

# Register an agent (enabling discovery)
await hub.register_agent(my_agent)

# Route a message (without dictating the response)
await hub.route_message(message)
```

## Example Usage

Recommended: define your AI agent using `AgentProfile` and pass it to `AIAgent(profile=...)`.

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity, AgentProfile, AgentType, Capability,
    ModelProvider, ModelName, InteractionMode,
)
from agentconnect.prebuilt import AIAgent, HumanAgent

async def main():
    load_dotenv()

    # Local registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Identities
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()

    # Define the AI agent via AgentProfile (recommended)
    ai_profile = AgentProfile(
        agent_id="research_agent",
        agent_type=AgentType.AI,
        name="Research Assistant",
        summary="Finds information and summarizes results",
        capabilities=[
            Capability(name="web_search", description="Search the web for information"),
        ],
    )

    # Instantiate agents
    ai_agent = AIAgent(
        agent_id=ai_profile.agent_id,
        identity=ai_identity,
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        profile=ai_profile,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and concise",
    )

    human = HumanAgent(
        agent_id="user123",
        name="User",
        identity=human_identity,
    )

    # Register both agents to enable discovery
    await hub.register_agent(human)
    await hub.register_agent(ai_agent)

    # Human starts an interaction with the AI
    asyncio.create_task(ai_agent.run())
    
    # Human agent sends a collaboration request to the research agent
    response = await hub.send_collaboration_request(
        sender_id=human.agent_id,
        receiver_id=ai_agent.agent_id,
        task_description="Search for the latest news on AI"
    )
    
    # The AI agent independently decides how to respond
    # The hub only ensures message delivery without controlling the response
    
    # When done, unregister agents and cleanup
    await ai_agent.stop()
    await hub.unregister_agent(human.agent_id)
    await hub.unregister_agent(ai_agent.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
```

Legacy initialization (still supported): pass `name` and `capabilities` directly to `AIAgent` without `profile`. Prefer the profile-based approach for richer discovery and consistent metadata.

## Configuration

You can toggle message history via `agentconnect.yaml`:

```yaml
communication:
  enable_message_history: true  # or false
```

When using a remote registry, you can pass a `RegistryAPIClient()` to `CommunicationHub`, which reads `settings.clients.registry.base_url`:

```python
from agentconnect.communication import CommunicationHub
from agentconnect.clients import RegistryAPIClient

hub = CommunicationHub(RegistryAPIClient())
```

## Best Practices

1. **Message Routing**: Use the hub for message delivery, not to control agent behavior.
2. **Security**: Identities are required; messages are signed and validated automatically.
3. **Agent Autonomy**: Design agents to make their own decisions about how to respond to messages.
4. **Capability Discovery**: Use collaboration flows to discover and leverage peer capabilities.
