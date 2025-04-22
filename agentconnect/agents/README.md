# Agents Module

The agents module provides independent agent implementations for the AgentConnect framework. Unlike traditional multi-agent systems that operate in a hierarchy, AgentConnect agents function as autonomous peers in a decentralized network, capable of discovering and collaborating with each other based on capabilities rather than pre-defined connections.

## Structure

```
agents/
├── __init__.py         # Package initialization and API exports
├── ai_agent.py         # AI agent implementation
├── human_agent.py      # Human agent implementation
├── telegram/           # Telegram agent implementation (see telegram/README.md)
└── README.md           # This file
```

## Agent Types

### AIAgent

The `AIAgent` class is an autonomous, independent AI implementation that can operate as a peer in a decentralized network. It provides:

- Independent operation with potential for internal multi-agent structures
- Dynamic discovery of other agents based on capabilities
- Secure, cryptographically verified communication
- Integration with various LLM providers (OpenAI, Anthropic, etc.)
- Independent decision-making and response generation
- Conversation memory and state management
- Rate limiting and cooldown mechanisms
- Workflow-based processing that can include its own internal agent system
- Tool integration for enhanced capabilities
- Optional payment capabilities for agent-to-agent transactions

Each AI agent can operate completely independently, potentially with its own internal multi-agent structure, while still being able to discover and communicate with other independent agents across the network.

#### Payment Integration

When created with `enable_payments=True`, the `AIAgent` integrates payment capabilities:

- **Wallet Setup**: Triggers wallet initialization in `BaseAgent.__init__`
- **AgentKit Tools**: Payment tools (e.g., `native_transfer`, `erc20_transfer`) are automatically added to the agent's workflow in `AIAgent._initialize_workflow`
- **LLM Decision Making**: The agent's LLM decides when to use payment tools based on prompt instructions in templates like `CORE_DECISION_LOGIC` and `PAYMENT_CAPABILITY_TEMPLATE`
- **Network Support**: Default support for Base Sepolia testnet, configurable to other networks
- **Transaction Verification**: Built-in transaction verification and confirmation

### HumanAgent

The `HumanAgent` class provides an interface for human users to interact with AI agents. It offers:

- Text-based interaction through console
- Message verification and security
- Conversation management
- Command processing (help, exit, etc.)

### TelegramAIAgent

The `TelegramAIAgent` class extends `AIAgent` to provide a Telegram bot interface, enabling:

- Natural language conversations with users via Telegram private chats
- Group chat interactions through bot mentions
- Media message handling (photos, documents, voice, etc.)
- Announcements to registered groups
- Integration with other AgentConnect agents via collaboration requests
- Concurrent processing of both Telegram messages and inter-agent communications

For more details, see the [Telegram Agent documentation](telegram/README.md).

## Key Features

### Decentralized Identity and Verification

All agents have their own independent identity with cryptographic verification, ensuring secure peer-to-peer communication between autonomous agents without requiring central authority. The identity includes:

- Agent ID
- Public/private key pairs for secure message signing and verification
- Independent verification methods

### Capability-Based Discovery

Instead of pre-defined connections, agents discover each other dynamically based on capabilities they advertise to the network:

- Capabilities define what services an agent can provide
- Agents can discover others with required capabilities
- Dynamic, runtime discovery enables truly decentralized operation
- No central control or predefined hierarchies

### Autonomous Operation

Each agent operates independently:

- Makes its own decisions
- Manages its own state
- Can have its own internal multi-agent structure
- Handles its own security and verification
- Participates in the network as a peer, not a subordinate

### Secure Communication

Built-in security prevents tampering and ensures message integrity:

- Cryptographic message signing
- Independent message verification
- Secure identity management
- End-to-end verified communication

### Rate Limiting

AI agents include built-in rate limiting to prevent excessive API usage:

- Token-based rate limiting (per minute and per hour)
- Cooldown periods when limits are reached
- Automatic recovery when cooldown expires

## Usage Examples

### Creating an Independent AI Agent

```python
from agentconnect.agents import AIAgent
from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, InteractionMode, Capability

# Define agent capabilities - these will be discoverable by other agents
capabilities = [
    Capability(
        name="research",
        description="Can perform internet research on any topic",
        input_schema={"query": "string"},
        output_schema={"results": "string"}
    ),
    Capability(
        name="summarization",
        description="Can summarize long texts",
        input_schema={"text": "string"},
        output_schema={"summary": "string"}
    )
]

# Create an autonomous AI agent
agent = AIAgent(
    agent_id="research_agent",
    name="Research Assistant",
    provider_type=ModelProvider.ANTHROPIC,
    model_name=ModelName.CLAUDE_3_OPUS,
    api_key="your-api-key",
    identity=AgentIdentity.create_key_based(),  # Independent cryptographic identity
    personality="helpful and knowledgeable research assistant",
    capabilities=capabilities,  # Advertised capabilities for discovery
    organization_id="org123",
    interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT]
)
```

### Creating a Human Agent

```python
from agentconnect.agents import HumanAgent
from agentconnect.core.types import AgentIdentity

# Create a human agent with identity
human = HumanAgent(
    agent_id="user123",
    name="John Doe",
    identity=AgentIdentity.create_key_based(),  # Cryptographic identity
    organization_id="org123"
)

# Start interaction with any AI agent in the network
await human.start_interaction(ai_agent)
```

### Autonomous Message Processing

```python
from agentconnect.core.message import Message
from agentconnect.core.types import MessageType

# Create a signed message
message = Message.create(
    sender_id="user123",
    receiver_id="research_agent",
    content="What can you tell me about quantum computing?",
    sender_identity=human.identity,  # Message is cryptographically signed
    message_type=MessageType.TEXT
)

# Agent autonomously processes the message and may collaborate with other agents as needed
response = await ai_agent.process_message(message)
```

## Integration with Decentralized Communication Hub

Agents connect to the decentralized network through the `CommunicationHub`:

```python
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry

# Create registry and hub for the decentralized network
registry = AgentRegistry()
hub = CommunicationHub(registry)

# Register independent agents to the network
await hub.register_agent(ai_agent)
await hub.register_agent(human)

# Agents can now discover and communicate with each other through capability-based routing
```

## Advanced Features

### Custom Tools

AI agents can implement their own internal multi-agent structures:

```python
from langchain_core.tools import BaseTool
from langchain.agents import AgentExecutor, create_react_agent

# Define custom tools and internal agents
custom_tools = [
    # Tools for the agent's internal system
]

# Create agent with its own internal agent system
agent = AIAgent(
    # ... other parameters ...
    custom_tools=custom_tools
)
```

### Autonomous Security

Agents handle their own message security:

```python
# Message is autonomously verified by the receiving agent
if not message.verify(agent.identity):
    # Agent independently decides to reject unverified messages
    return Message.create(
        sender_id=agent.agent_id,
        receiver_id=message.sender_id,
        content="Message verification failed. Communication rejected.",
        sender_identity=agent.identity,
        message_type=MessageType.ERROR,
        metadata={"error_type": "security_verification_failed"}
    )
```

## Best Practices

1. **Unique Agent Identities**: Always use unique IDs for each agent to prevent conflicts in the decentralized network.
2. **Secure API Keys**: Never hardcode API keys; use environment variables or secure storage.
3. **Capability Design**: Design clear, well-defined capabilities that other agents can discover and use.
4. **Autonomous Error Handling**: Implement proper error handling for agent interactions without central coordination.
5. **Resource Management**: Be mindful of resource usage when creating multiple independent AI agents.
6. **Secure Communication**: Always verify message signatures to maintain security in the decentralized network.
7. **Autonomous Operation**: Design agents that can make independent decisions without central control.
8. **Secure CDP Keys**: When using `enable_payments=True`, ensure CDP API keys are handled securely and never exposed.
