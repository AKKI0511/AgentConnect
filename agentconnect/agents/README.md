# Agents Module

The agents module provides the core agent implementations for the AgentConnect framework. These agents can communicate with each other, process messages, and execute tasks based on their capabilities.

## Structure

```
agents/
├── __init__.py         # Package initialization and API exports
├── ai_agent.py         # AI agent implementation
├── human_agent.py      # Human agent implementation
└── README.md           # This file
```

## Agent Types

### AIAgent

The `AIAgent` class is the primary implementation for AI-powered agents. It provides:

- Integration with LLM providers (OpenAI, Anthropic, etc.)
- Message processing and response generation
- Conversation memory management
- Rate limiting and cooldown mechanisms
- Workflow-based processing using LangGraph
- Tool integration for enhanced capabilities

### HumanAgent

The `HumanAgent` class provides an interface for human users to interact with AI agents. It offers:

- Text-based interaction through console
- Message verification and security
- Conversation management
- Command processing (help, exit, etc.)

## Key Features

### Identity and Verification

All agents have an identity that can be verified, ensuring secure communication between agents. The identity includes:

- Agent ID
- Public/private key pairs
- Verification methods

### Capabilities

Agents can define their capabilities, which are functions or services they can provide to other agents. Capabilities include:

- Name and description
- Input and output schemas
- Implementation details

### Conversation Management

Agents maintain conversation state with other agents, including:

- Active conversations
- Message history
- System messages for context

### Rate Limiting

AI agents include built-in rate limiting to prevent excessive API usage:

- Token-based rate limiting (per minute and per hour)
- Cooldown periods when limits are reached
- Automatic recovery when cooldown expires

## Usage Examples

### Creating an AI Agent

```python
from agentconnect.agents import AIAgent
from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, InteractionMode

# Create an AI agent
agent = AIAgent(
    agent_id="research_agent",
    name="Research Assistant",
    provider_type=ModelProvider.ANTHROPIC,
    model_name=ModelName.CLAUDE_3_OPUS,
    api_key="your-api-key",
    identity=AgentIdentity.create_key_based(),
    personality="helpful and knowledgeable research assistant",
    organization_id="org123",
    interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
    max_tokens_per_minute=5500,
    max_tokens_per_hour=100000
)
```

### Creating a Human Agent

```python
from agentconnect.agents import HumanAgent
from agentconnect.core.types import AgentIdentity

# Create a human agent
human = HumanAgent(
    agent_id="user123",
    name="John Doe",
    identity=AgentIdentity.create_key_based(),
    organization_id="org123"
)

# Start interaction with an AI agent
await human.start_interaction(ai_agent)
```

### Processing Messages

```python
from agentconnect.core.message import Message
from agentconnect.core.types import MessageType

# Create a message
message = Message.create(
    sender_id="user123",
    receiver_id="research_agent",
    content="What can you tell me about quantum computing?",
    sender_identity=human.identity,
    message_type=MessageType.TEXT
)

# Process the message
response = await ai_agent.process_message(message)
```

## Integration with Communication Hub

Agents are designed to work with the `CommunicationHub` for message routing:

```python
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry

# Create registry and hub
registry = AgentRegistry()
hub = CommunicationHub(registry)

# Register agents
await hub.register_agent(ai_agent)
await hub.register_agent(human)

# Now agents can communicate through the hub
```

## Advanced Features

### Custom Tools

AI agents can be enhanced with custom tools:

```python
from langchain_core.tools import BaseTool

# Define custom tools
custom_tools = [
    # Your custom tools here
]

# Create agent with custom tools
agent = AIAgent(
    # ... other parameters ...
    custom_tools=custom_tools
)
```

### Memory Management

AI agents support different memory types:

```python
from agentconnect.agents import AIAgent, MemoryType

# Create agent with specific memory type
agent = AIAgent(
    # ... other parameters ...
    memory_type=MemoryType.BUFFER
)
```

## Best Practices

1. **Unique Agent IDs**: Always use unique IDs for each agent to prevent conflicts.
2. **Secure API Keys**: Never hardcode API keys; use environment variables or secure storage.
3. **Error Handling**: Implement proper error handling for agent interactions.
4. **Rate Limiting**: Be mindful of rate limits when creating multiple AI agents.
5. **Resource Cleanup**: Always unregister agents from the hub when they're no longer needed.
6. **Absolute Imports**: Use absolute imports for clarity and consistency.
7. **Type Hints**: Always use type hints for better IDE support and static analysis.
8. **Comprehensive Documentation**: Document all classes, methods, and parameters. 