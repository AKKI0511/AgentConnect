# Core Module

The core module provides the foundational components of the AgentConnect framework. These components form the essential building blocks for agent-based systems, including agent identity, messaging, registration, and type definitions.

## Structure

```
core/
├── __init__.py              # Package initialization and API exports
├── agent.py                 # BaseAgent abstract class
├── exceptions.py            # Core exception definitions
├── message.py               # Message class for agent communication
├── types.py                 # Core type definitions and enumerations
├── payment_constants.py     # Constants for payment functionality
├── registry/                # Agent registry and discovery subsystem
│   ├── __init__.py          # Registry package exports
│   ├── registry_base.py     # AgentRegistry implementation
│   ├── registration.py      # Agent registration data structures
│   ├── capability_discovery.py  # Capability discovery service
│   ├── identity_verification.py # Identity verification logic
│   └── capability_discovery_impl/ # Implementation details for vector search
└── README.md                # This file
```

## Key Components

### BaseAgent (`agent.py`)

The `BaseAgent` class is an abstract base class that defines the core functionality for all agents in the system. It provides:

- **Identity Management**: Verification of agent identities using DIDs (Decentralized Identifiers)
- **Message Handling**: Sending, receiving, and processing messages
- **Capability Declaration**: Defining what an agent can do
- **Conversation Management**: Tracking and managing conversations between agents
- **Cooldown Mechanism**: Rate limiting to prevent overloading
- **Payment Capabilities**: Optional integration with Coinbase Developer Platform (CDP)

Key methods:
- `send_message()`: Send a message to another agent
- `receive_message()`: Process an incoming message
- `process_message()`: Abstract method that must be implemented by subclasses
- `verify_identity()`: Verify the agent's identity using its DID
- `run()`: Start the agent's message processing loop
- `stop()`: Stop the agent and clean up resources

Developers must implement these abstract methods when extending `BaseAgent`:
- `_initialize_llm()`: Initialize the agent's language model
- `_initialize_workflow()`: Initialize the agent's workflow

### Agent Registry System (`registry/`)

The registry subsystem provides a comprehensive solution for agent discovery, capability matching, and identity verification:

#### AgentRegistry (`registry/registry_base.py`)

The registry for agent discovery and management:

- **Agent Registration**: Register agents with their capabilities
- **Capability Indexing**: Index agent capabilities for fast lookup
- **Agent Lifecycle Management**: Track agent status and handle registration/unregistration
- **Organization Management**: Group agents by organization
- **Vector Search Integration**: Coordinate with the capability discovery service
- **Payment Address Storage**: Store and provide agent payment addresses during discovery

Key methods:
- `register()`: Register an agent with the registry
- `unregister()`: Remove an agent from the registry
- `update_registration()`: Update an agent's registration information
- `get_by_capability()`: Find agents with a specific capability
- `get_by_capability_semantic()`: Find agents with capabilities that semantically match a description
- `get_all_capabilities()`: Get a list of all available capabilities
- `get_all_agents()`: Get a list of all registered agents
- `get_agent_type()`: Get the type of a registered agent
- `get_by_interaction_mode()`: Find agents supporting a specific interaction mode
- `get_by_organization()`: Find agents belonging to a specific organization
- `get_verified_agents()`: Get a list of verified agents

Note: The `is_agent_active()` method is not available in the registry but is provided by the `CommunicationHub` class in the `communication` module.

For more details on the registry and its methods, see the [Agent Registry documentation](registry/README.md).

#### AgentRegistration (`registry/registration.py`)

Data structure for agent registration information:

- **Agent profile information**:
    - **Agent ID**: Unique identifier for the agent
    - **Agent Type**: Type of agent (e.g. "human", "ai")
    - **Interaction Modes**: Supported interaction modes
    - **Identity**: Agent identity credentials
    - **Name, Summary, Description**: Information about the agent
    - **Version, Documentation URL**: Version and documentation information
    - **Organization, Developer**: Information about the agent's organization and developer
    - **URL, Auth Schemes**: Endpoint URL and authentication information
    - **Input/Output Modes**: Supported input and output modes
    - **Capabilities, Skills**: Agent capabilities and skills
    - **Examples, Tags**: Example use cases and search tags
    - **Payment Address**: Optional cryptocurrency address for agent-to-agent payments
    - **Custom Metadata**: Additional information about the agent

#### CapabilityDiscoveryService (`registry/capability_discovery.py`)

Service for semantic capability discovery:

- **Embedding Generation**: Generate embeddings for capability descriptions
- **Vector Search**: Find capabilities that semantically match a description
- **Filtering**: Filter results based on agent attributes
- **Similarity Scoring**: Rank results by similarity to the query

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
- `_get_signable_content()`: Get message content for signing/verification

### Types (`types.py`)

The `types.py` file defines core types used throughout the framework:

- **ModelProvider**: Supported AI model providers (OpenAI, Anthropic, Groq, Google)
- **ModelName**: Specific model names for each provider, with `get_default_for_provider()` method
- **AgentType**: Types of agents (Human, AI)
- **InteractionMode**: Modes of interaction (Human-to-Agent, Agent-to-Agent)
- **ProtocolVersion**: Supported protocol versions
- **VerificationStatus**: Status of agent identity verification
- **Capability**: Structure for defining agent capabilities
- **AgentIdentity**: Decentralized identity for agents with cryptographic key methods:
  - `create_key_based()`: Create a new key-based identity
  - `sign_message()`: Sign a message using the private key
  - `verify_signature()`: Verify a signature using the public key
  - `to_dict()`: Convert identity to dictionary format
  - `from_dict()`: Create identity from dictionary format
- **MessageType**: Types of messages that can be exchanged
- **NetworkMode**: Network modes for agent communication
- **AgentMetadata**: Agent information including optional payment address
- **Skill**: Structure for defining agent skills
- **AgentProfile**: Comprehensive profile for an agent

### Payment Integration

The core module integrates with the Coinbase Developer Platform (CDP) for payment capabilities:

- **BaseAgent Wallet Setup**: `BaseAgent.__init__` conditionally initializes agent wallets when `enable_payments=True`
- **Payment Address Storage**: `payment_address` field in `AgentProfile` and `AgentRegistration` 
- **Payment Constants**: Default token symbol and amounts defined in `payment_constants.py`
- **Capability Discovery**: Payment addresses are included in agent search results

For details on how agents use payment capabilities, see `agentconnect/agents/README.md`.

### Exceptions (`exceptions.py`)

The `exceptions.py` file defines custom exceptions used throughout the framework:

- **SecurityError**: Errors during message verification
- **AgentError**: Base class for agent-related errors
- **RegistrationError**: Errors during agent registration
- **CommunicationError**: Errors during agent communication
- **CapabilityError**: Errors related to agent capabilities
- **ConfigurationError**: Errors related to configuration

## Usage Examples

### Creating an Agent

```python
from agentconnect.core import BaseAgent, AgentType, AgentIdentity, InteractionMode
from agentconnect.core.types import Capability, AgentProfile

class MyAgent(BaseAgent):
    def __init__(self, agent_id, name):
        capabilities = [
            Capability(
                name="text_processing",
                description="Process text input and generate a response",
            )
        ]
        profile = AgentProfile(
            agent_id=agent_id,
            agent_type=AgentType.AI,
            name=name,
            capabilities=capabilities
        )

        super().__init__(
            agent_id=agent_id,
            identity=AgentIdentity.create_key_based(),
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            profile=profile,
            enable_payments=True,
            wallet_data_dir="./wallet_data"
        )
        self.name = name

    def _initialize_llm(self):
        # Implement LLM initialization
        pass

    def _initialize_workflow(self):
        # Implement workflow initialization
        pass

    async def process_message(self, message):
        # Implement message processing logic
        return None  # Or return a response message
```

### Sending and Receiving Messages

```python
from agentconnect.core import Message, MessageType

# Create a message directly
message = Message.create(
    sender_id="agent1",
    receiver_id="agent2",
    content="Hello, agent2!",
    sender_identity=agent1.identity,
    message_type=MessageType.TEXT
)

# Send a message using the agent's send_message method
response_message = await agent1.send_message(
    receiver_id="agent2",
    content="Hello, agent2!",
    message_type=MessageType.TEXT
)

# Process a received message
response = await agent2.process_message(message)
```

### Registering Agents and Finding by Capability

```python
from agentconnect.core.registry import AgentRegistry
from agentconnect.communication.hub import CommunicationHub

# Create a registry with in-memory vector store
registry = AgentRegistry({"in_memory": True})

# Create a communication hub with the registry
hub = CommunicationHub(registry)

# Register an agent with the hub - this is the recommended approach
# The hub creates the AgentRegistration and registers with the registry automatically
await hub.register_agent(agent)

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
    
    # Get agent type
    agent_type = await registry.get_agent_type(agent.agent_id)
    
    # Check if an agent is active using the hub
    is_active = await hub.is_agent_active(agent.agent_id)
```

For more details on the registry configuration and capabilities, see the [Agent Registry documentation](registry/README.md).

## Semantic Search Features

The registry's semantic search capabilities provide powerful ways to find agents:

### Basic Usage

```python
# Find agents that can summarize text
agents = await registry.get_by_capability_semantic("summarize text")

# Find agents with data analysis capabilities with custom parameters
agents = await registry.get_by_capability_semantic(
    "analyze data and create visualizations",
    limit=3,  # Return at most 3 agents
    similarity_threshold=0.5  # Only return agents with similarity scores >= 0.5
)

# Find agents with filtering
agents = await registry.get_by_capability_semantic(
    "translate text between languages",
    filters={
        "agent_type": [AgentType.AI.value],  # Only AI agents
        "interaction_modes": [InteractionMode.AGENT_TO_AGENT.value]  # Only agent-to-agent
    }
)
```

### Advanced Configuration

```python
# Configure the agent registry with custom vector store settings
vector_store_config = {
    "in_memory": True,  # Use an in-memory vector store
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",  # Use a smaller, faster model
    "cache_folder": "./embeddings_cache",  # Specify cache location
    "vector_store_path": "./.cache/vector_stores"  # Path for persistent vector storage
}

registry = AgentRegistry(vector_store_config=vector_store_config)

# Register agents...
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
2. **Implement Required Methods**: Provide concrete implementations of the abstract methods `_initialize_llm()`, `_initialize_workflow()`, and `process_message()`
3. **Register Capabilities**: Clearly define agent capabilities during registration
4. **Include Detailed Descriptions**: Add comprehensive descriptions to capabilities for better semantic matching
5. **Register via Hub**: Always register agents through the CommunicationHub rather than creating AgentRegistration objects manually
6. **Handle Message Types**: Properly handle different message types in your agent implementation
7. **Verify Messages**: Always verify message signatures before processing
8. **Use Semantic Search**: Leverage semantic search for more flexible capability matching
9. **Adjust Similarity Thresholds**: Fine-tune thresholds based on your specific use case
10. **Manage Conversations**: Properly track and manage conversations between agents
11. **Use Absolute Imports**: Always use absolute imports for clarity and consistency
12. **Add Type Hints**: Use type hints for better IDE support and static analysis
13. **Document Your Code**: Add comprehensive docstrings to all classes and methods
14. **Enable Payments When Needed**: Only enable payments when required to avoid unnecessary initialization
15. **Secure Wallet Data**: When using payment capabilities, ensure wallet data is stored securely
