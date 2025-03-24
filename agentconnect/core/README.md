# Core Module

The core module provides the foundational components of the AgentConnect framework. These components form the essential building blocks for agent-based systems, including agent identity, messaging, registration, and type definitions.

## Structure

```
core/
├── __init__.py         # Package initialization and API exports
├── agent.py            # BaseAgent abstract class
├── message.py          # Message class for agent communication
├── registry.py         # AgentRegistry for agent discovery
├── types.py            # Core type definitions and enumerations
└── README.md           # This file
```

## Key Components

### BaseAgent (`agent.py`)

The `BaseAgent` class is an abstract base class that defines the core functionality for all agents in the system. It provides:

- **Identity Management**: Verification of agent identities using DIDs (Decentralized Identifiers)
- **Message Handling**: Sending, receiving, and processing messages
- **Capability Declaration**: Defining what an agent can do
- **Conversation Management**: Tracking and managing conversations between agents
- **Cooldown Mechanism**: Rate limiting to prevent overloading

Key methods:
- `send_message()`: Send a message to another agent
- `receive_message()`: Process an incoming message
- `process_message()`: Abstract method that must be implemented by subclasses
- `verify_identity()`: Verify the agent's identity using its DID

### AgentRegistry (`registry.py`)

The `AgentRegistry` class provides a centralized registry for agent discovery and capability matching. It supports:

- **Agent Registration**: Register agents with their capabilities
- **Capability Discovery**: Find agents with specific capabilities
- **Semantic Search**: Find agents with capabilities that match a description
- **Identity Verification**: Verify agent identities during registration
- **Organization Management**: Group agents by organization

Key methods:
- `register()`: Register an agent with the registry
- `unregister()`: Remove an agent from the registry
- `get_by_capability()`: Find agents with a specific capability
- `get_by_capability_semantic()`: Find agents with capabilities that semantically match a description
- `get_all_capabilities()`: Get a list of all available capabilities
- `get_all_agents()`: Get a list of all registered agents

### Message (`message.py`)

The `Message` class defines the structure of messages exchanged between agents. It includes:

- **Message Content**: The actual content of the message
- **Metadata**: Additional information about the message
- **Signatures**: Cryptographic signatures for message verification
- **Protocol Information**: Version and type information for protocol compatibility

Key methods:
- `create()`: Create a new signed message
- `sign()`: Sign a message with the sender's private key
- `verify()`: Verify a message signature using the sender's public key

### Types (`types.py`)

The `types.py` file defines core types used throughout the framework:

- **ModelProvider**: Supported AI model providers (OpenAI, Anthropic, Groq, Google)
- **ModelName**: Specific model names for each provider
- **AgentType**: Types of agents (Human, AI)
- **InteractionMode**: Modes of interaction (Human-to-Agent, Agent-to-Agent)
- **Capability**: Structure for defining agent capabilities
- **AgentIdentity**: Decentralized identity for agents
- **MessageType**: Types of messages that can be exchanged
- **ProtocolVersion**: Supported protocol versions

## Usage Examples

### Creating an Agent

```python
from agentconnect.core import BaseAgent, AgentType, AgentIdentity, InteractionMode, Capability

class MyAgent(BaseAgent):
    def __init__(self, agent_id, name):
        capabilities = [
            Capability(
                name="text_processing",
                description="Process text input and generate a response",
                input_schema={"text": "string"},
                output_schema={"response": "string"}
            )
        ]

        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.AI,
            identity=AgentIdentity.create_key_based(),
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
            capabilities=capabilities
        )
        self.name = name

    def _initialize_llm(self):
        # Implement LLM initialization
        pass

    def _initialize_workflow(self):
        # Implement workflow initialization
        pass

    async def process_message(self, message):
        # Implement message processing
        pass
```

### Sending and Receiving Messages

```python
from agentconnect.core import Message, MessageType

# Create a message
message = Message.create(
    sender_id="agent1",
    receiver_id="agent2",
    content="Hello, agent2!",
    sender_identity=agent1.identity,
    message_type=MessageType.TEXT
)

# Send the message
await agent1.send_message(
    receiver_id="agent2",
    content="Hello, agent2!",
    message_type=MessageType.TEXT
)

# Process a received message
response = await agent2.process_message(message)
```

### Registering Agents

```python
from agentconnect.core import AgentRegistry, AgentRegistration

# Create a registry
registry = AgentRegistry()

# Register an agent
registration = AgentRegistration(
    agent_id=agent.agent_id,
    organization_id="org1",
    agent_type=agent.metadata.agent_type,
    interaction_modes=agent.metadata.interaction_modes,
    capabilities=agent.capabilities,
    identity=agent.identity
)

success = await registry.register(registration)

# Find agents by capability
agents = await registry.get_by_capability("text_processing")

# Find agents by semantic search
agents = await registry.get_by_capability_semantic("process text and generate responses")
```

## Integration with LangGraph

The core framework is designed to work seamlessly with LangGraph for workflow management. Key integration points:

1. **BaseAgent.process_message()**: Abstract method implemented by subclasses to process messages using LangGraph workflows
2. **Conversation IDs**: Generated using `_get_conversation_id()` to maintain conversation context in LangGraph
3. **Message Correlation**: Messages include metadata for correlation with LangGraph workflows

## Security Features

Security is a core feature of the framework:

1. **DID-based Identity**: Agents have decentralized identifiers for secure identity management
2. **Message Signing**: Messages are signed with the sender's private key
3. **Signature Verification**: Message signatures are verified using the sender's public key
4. **Identity Verification**: Agent identities are verified during registration

## Best Practices

When working with the core framework:

1. **Extend BaseAgent**: Create custom agent types by extending the `BaseAgent` class
2. **Implement Required Methods**: Provide concrete implementations of the abstract methods
3. **Register Capabilities**: Clearly define agent capabilities during registration
4. **Handle Message Types**: Properly handle different message types in your agent implementation
5. **Verify Messages**: Always verify message signatures before processing
6. **Use Semantic Search**: Leverage semantic search for more flexible capability matching
7. **Manage Conversations**: Properly track and manage conversations between agents
8. **Use Absolute Imports**: Always use absolute imports for clarity and consistency
9. **Add Type Hints**: Use type hints for better IDE support and static analysis
10. **Document Your Code**: Add comprehensive docstrings to all classes and methods
