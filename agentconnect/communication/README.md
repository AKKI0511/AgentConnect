# Communication Module

The communication module provides the infrastructure for agent communication in the AgentConnect framework. It handles message routing, agent registration, and protocol management.

## Structure

```
communication/
├── __init__.py         # Package initialization and API exports
├── hub.py              # CommunicationHub implementation
├── protocols/          # Communication protocol implementations
│   ├── __init__.py     # Protocol API exports
│   ├── base.py         # BaseProtocol abstract class
│   ├── agent.py        # SimpleAgentProtocol implementation
│   └── collaboration.py # CollaborationProtocol implementation
└── README.md           # This file
```

## Key Components

### CommunicationHub

The `CommunicationHub` is the central component that:
- Registers and unregisters agents
- Routes messages between agents
- Manages communication protocols
- Tracks message history
- Handles special message types (cooldown, stop, etc.)

```python
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry

# Create a hub
registry = AgentRegistry()
hub = CommunicationHub(registry)

# Register an agent
await hub.register_agent(my_agent)

# Route a message
await hub.route_message(message)
```

### Protocols

The communication module includes several protocol implementations:

1. **BaseProtocol**: Abstract base class for all protocols
2. **SimpleAgentProtocol**: Basic agent-to-agent communication
3. **CollaborationProtocol**: Advanced protocol for agent collaboration

```python
from agentconnect.communication import SimpleAgentProtocol

# Create a protocol instance
protocol = SimpleAgentProtocol()

# Format a message
message = await protocol.format_message(
    sender_id="agent1",
    receiver_id="agent2",
    content="Hello!",
    sender_identity=identity,
    message_type=MessageType.TEXT
)

# Validate a message
is_valid = await protocol.validate_message(message)
```

## Best Practices

1. **Message Routing**: Always use the `CommunicationHub` for routing messages between agents.
2. **Protocol Selection**: Use the appropriate protocol for your communication needs.
3. **Error Handling**: Handle communication errors gracefully using the error message types.
4. **Asynchronous Operations**: All communication operations are asynchronous and should be awaited.

## Example Usage

```python
import asyncio
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import MessageType
from agentconnect.agents import AIAgent, HumanAgent

async def main():
    # Initialize registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create and register agents
    human = HumanAgent(...)
    ai = AIAgent(...)
    
    await hub.register_agent(human)
    await hub.register_agent(ai)
    
    # Send a message
    await human.send_message(
        receiver_id=ai.agent_id,
        content="Hello, AI!",
        message_type=MessageType.TEXT
    )
    
    # Wait for and process responses
    # ...
    
    # Unregister agents when done
    await hub.unregister_agent(human.agent_id)
    await hub.unregister_agent(ai.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
```
