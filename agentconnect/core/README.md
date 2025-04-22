# Core Module

The core module provides the foundational components of the AgentConnect framework. These components form the essential building blocks for agent-based systems, including agent identity, messaging, registration, and type definitions.

## Structure

```
core/
├── __init__.py         # Package initialization and API exports
├── agent.py            # BaseAgent abstract class
├── exceptions.py       # Core exception definitions
├── message.py          # Message class for agent communication
├── types.py            # Core type definitions and enumerations
├── registry/           # Agent registry and discovery subsystem
│   ├── __init__.py     # Registry package exports
│   ├── registry_base.py        # AgentRegistry implementation
│   ├── capability_discovery.py # Semantic search for capabilities
│   ├── identity_verification.py # Agent identity verification
│   └── registration.py         # Agent registration data structures
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

### Agent Registry System (`registry/`)

The registry subsystem provides a comprehensive solution for agent discovery, capability matching, and identity verification. It's been refactored into multiple specialized components for better maintainability and extensibility:

#### AgentRegistry (`registry/registry_base.py`)

The central registry for agent discovery and management:

- **Agent Registration**: Register agents with their capabilities
- **Capability Indexing**: Index agent capabilities for fast lookup
- **Agent Lifecycle Management**: Track agent status and handle registration/unregistration
- **Organization Management**: Group agents by organization
- **Vector Search Integration**: Coordinate with the capability discovery service
- **Payment Address Storage**: Store and provide agent payment addresses during discovery

Key methods:
- `register()`: Register an agent with the registry
- `unregister()`: Remove an agent from the registry
- `get_by_capability()`: Find agents with a specific capability
- `get_by_capability_semantic()`: Find agents with capabilities that semantically match a description
- `get_all_capabilities()`: Get a list of all available capabilities
- `get_all_agents()`: Get a list of all registered agents
- `is_agent_active()`: Check if an agent is active and available
- `get_agent_type()`: Get the type of a registered agent

#### CapabilityDiscoveryService (`registry/capability_discovery.py`)

Specialized component for semantic search and capability matching:

- **Vector-Based Semantic Search**: Find semantically similar capabilities using embeddings
- **Multiple Vector Store Backends**: Support for FAISS and USearch vector stores
- **Similarity Scoring**: Calculate and normalize similarity scores between capabilities
- **Fallback Mechanisms**: Graceful degradation to simpler matching when vector search unavailable
- **Embedding Model Management**: Efficient handling of embedding models for semantic search

Key methods:
- `initialize_embeddings_model()`: Initialize the embeddings model for semantic search
- `find_by_capability_semantic()`: Find agents with capabilities that semantically match a description
- `find_by_capability_name()`: Find agents by exact capability name matching
- `precompute_all_capability_embeddings()`: Precompute embeddings for efficient searching
- `save_vector_store()` / `load_vector_store()`: Persistence for vector stores

#### Identity Verification (`registry/identity_verification.py`)

Handles verification of agent identities:

- **DID Verification**: Verify Decentralized Identifiers
- **Public Key Verification**: Verify agent public keys
- **Signature Verification**: Verify digital signatures
- **Trust Chains**: Verify trust chains for agent identities

#### AgentRegistration (`registry/registration.py`)

Data structure for agent registration information:

- **Agent Metadata**: Basic information about the agent
- **Capabilities**: List of agent capabilities
- **Identity Information**: Agent identity credentials
- **Organization Details**: Information about the agent's organization
- **Payment Address**: Optional cryptocurrency address for agent-to-agent payments

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
- **AgentMetadata**: Agent information including optional payment address

### Payment Integration

The core module integrates with the Coinbase Developer Platform (CDP) for payment capabilities:

- **BaseAgent Wallet Setup**: `BaseAgent.__init__` conditionally initializes agent wallets when `enable_payments=True`
- **Payment Address Storage**: `payment_address` field in `AgentMetadata` and `AgentRegistration` 
- **Payment Constants**: Default token symbol and amounts defined in `payment_constants.py`
- **Capability Discovery**: Payment addresses are included in agent search results

For details on how agents use payment capabilities, see `agentconnect/agents/README.md`.

### Exceptions (`exceptions.py`)

The `exceptions.py` file defines custom exceptions used throughout the framework:

- **RegistrationError**: Errors during agent registration
- **IdentityVerificationError**: Errors during identity verification
- **MessageError**: Errors related to message handling
- **AgentError**: Base class for agent-related errors

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

### Registering Agents and Finding by Capability

```python
from agentconnect.core.registry import AgentRegistry, AgentRegistration

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

# Find agents by capability (exact match)
agents = await registry.get_by_capability("text_processing")

# Find agents by semantic search with custom threshold
# Returns a list of (agent, similarity_score) tuples
agents_with_scores = await registry.get_by_capability_semantic(
    "analyze text and generate summaries", 
    limit=5,
    similarity_threshold=0.3
)

# Get agent details
for agent, score in agents_with_scores:
    print(f"Agent: {agent.agent_id}, Score: {score:.2f}")
    
    # Check if agent is active
    is_active = await registry.is_agent_active(agent.agent_id)
    
    # Get agent type
    agent_type = await registry.get_agent_type(agent.agent_id)
```

## Semantic Search Features

The registry's semantic search capabilities provide powerful ways to find agents:

### Basic Usage

```python
# Find agents that can summarize text
agents = await registry.get_by_capability_semantic("summarize text")

# Find agents with data analysis capabilities
agents = await registry.get_by_capability_semantic(
    "analyze data and create visualizations",
    limit=3,  # Return at most 3 agents
    similarity_threshold=0.5  # Only return agents with similarity scores >= 0.5
)
```

### Advanced Configuration

```python
# Configure the agent registry with custom vector store settings
vector_store_config = {
    "prefer_backend": "faiss",  # Use FAISS for vector storage
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",  # Use a smaller, faster model
    "cache_folder": "./embeddings_cache"  # Specify cache location
}

registry = AgentRegistry(vector_store_config=vector_store_config)

# Register agents...

# Save vector store for faster startup next time
await registry.save_vector_store("./vector_store")

# Later, load the saved vector store
await registry.load_vector_store("./vector_store")
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
4. **Identity Verification**: Agent identities are verified during registration through the dedicated identity verification module

## Best Practices

When working with the core framework:

1. **Extend BaseAgent**: Create custom agent types by extending the `BaseAgent` class
2. **Implement Required Methods**: Provide concrete implementations of the abstract methods
3. **Register Capabilities**: Clearly define agent capabilities during registration
4. **Include Detailed Descriptions**: Add comprehensive descriptions to capabilities for better semantic matching
5. **Handle Message Types**: Properly handle different message types in your agent implementation
6. **Verify Messages**: Always verify message signatures before processing
7. **Use Semantic Search**: Leverage semantic search for more flexible capability matching
8. **Adjust Similarity Thresholds**: Fine-tune thresholds based on your specific use case
9. **Manage Conversations**: Properly track and manage conversations between agents
10. **Use Absolute Imports**: Always use absolute imports for clarity and consistency
11. **Add Type Hints**: Use type hints for better IDE support and static analysis
12. **Document Your Code**: Add comprehensive docstrings to all classes and methods
