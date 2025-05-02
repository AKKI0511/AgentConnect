# Registry Subsystem

The Registry subsystem provides a comprehensive solution for agent discovery, capability matching, and identity verification in the AgentConnect framework. It has been designed with modularity, performance, and extensibility in mind.

## Directory Structure

```
registry/
├── __init__.py                # Package exports
├── registry_base.py           # AgentRegistry implementation
├── capability_discovery.py    # Semantic search for capabilities
├── identity_verification.py   # Agent identity verification
├── registration.py            # Agent registration data structures
└── README.md                  # This documentation file
```

## Components

### AgentRegistry (`registry_base.py`)

The central registry for agent discovery and management:

- **Agent Registration & Indexing**: Maintains a registry of agents and their capabilities with efficient indexing
- **Capability Lookup**: Provides both exact and semantic matching of capabilities 
- **Agent Lifecycle Management**: Tracks agent availability and status
- **Organization Grouping**: Organizes agents by organization
- **Payment Address Handling**: Stores the optional `payment_address` provided during registration and makes it available during discovery, facilitating agent economy features.

The `AgentRegistry` class acts as a facade for the entire registry subsystem, coordinating between the specialized components and providing a unified API for agent registration and discovery.

### CapabilityDiscoveryService (`capability_discovery.py`)

Specialized component for semantic search and capability matching:

- **Vector Embeddings**: Uses text embeddings to represent agent capabilities
- **Multiple Vector Backends**: Supports different vector store backends (FAISS, USearch)
- **Flexible Matching**: Finds agents with capabilities that semantically match a description
- **Similarity Scoring**: Ranks agents by capability relevance with normalized scores
- **Graceful Degradation**: Falls back to simpler matching when vector search is unavailable

The service handles the complex task of semantic similarity matching to find agents with capabilities that match a description, even when the capabilities aren't an exact text match.

### IdentityVerificationService (`identity_verification.py`)

Manages verification of agent identities:

- **DID Verification**: Verifies decentralized identifiers (DIDs)
- **Public Key Verification**: Verifies agent public keys
- **Signature Validation**: Validates digital signatures
- **Trust Chains**: Validates trust chains for agent identities

This component ensures that agent identities are valid and trusted before allowing them to register and interact with other agents.

### AgentRegistration (`registration.py`)

Data structure for agent registration information:

- **Agent Metadata**: Basic information about the agent
- **Capabilities**: List of agent capabilities
- **Identity Information**: Agent identity credentials
- **Organization Details**: Information about the agent's organization

This is the fundamental data structure used to register agents with the registry.

## Key Features

### Semantic Capability Matching

The registry's semantic matching enables finding agents based on capability descriptions rather than exact names:

```python
# Find agents that can analyze data
agents = await registry.get_by_capability_semantic("analyze data and create visualizations")

# Find agents that can write code
agents = await registry.get_by_capability_semantic("generate Python code from requirements")
```

This enables more natural, human-like capability discovery compared to exact string matching.

### Vector Store Backends

The registry supports multiple vector store backends:

- **FAISS**: High-performance vector similarity search (recommended for production)
- **USearch**: Lighter alternative for simpler deployments

Backend selection is automatic based on available dependencies, with fallbacks to ensure functionality.

### Similarity Scoring and Thresholds

Results from semantic searches include normalized similarity scores:

```python
# Find agents with similarity scores
results = await registry.get_by_capability_semantic("translate text")

for agent, score in results:
    print(f"Agent: {agent.agent_id}, Similarity: {score:.2f}")
```

You can adjust the threshold to control result quality:

```python
# Only return high-confidence matches
results = await registry.get_by_capability_semantic(
    "translate text from English to Spanish",
    similarity_threshold=0.7  # Higher threshold = higher quality matches
)
```

### Registry Persistence

The registry can save and load vector stores for faster initialization:

```python
# Save the vector store after registering agents
await registry.save_vector_store("./vector_store")

# Later, load the vector store for faster startup
await registry.load_vector_store("./vector_store")
```

This allows for faster startup times in production environments.

## Using the Registry

### Basic Registration and Discovery

```python
from agentconnect.core.registry import AgentRegistry, AgentRegistration
from agentconnect.core.types import Capability, AgentType

# Create a registry
registry = AgentRegistry()

# Create a capability
capability = Capability(
    name="text_translation",
    description="Translate text between languages with high accuracy"
)

# Register an agent
registration = AgentRegistration(
    agent_id="translator_agent",
    agent_type=AgentType.AI,
    capabilities=[capability],
    # ... other registration details
)

# Register the agent
await registry.register(registration)

# Find agents by exact capability name
agents = await registry.get_by_capability("text_translation")

# Find agents by semantic capability description
agents_with_scores = await registry.get_by_capability_semantic(
    "translate English to Spanish"
)
```

### Advanced Configuration

```python
# Configure the registry with custom vector store settings
vector_store_config = {
    "prefer_backend": "faiss",    # Prefer FAISS backend
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",  # Smaller embedding model
    "cache_folder": "./cache",    # Custom cache location
}

# Create registry with custom config
registry = AgentRegistry(vector_store_config=vector_store_config)

# Register agents...

# Get all capabilities in the registry
all_capabilities = await registry.get_all_capabilities()

# Get all agents in the registry
all_agents = await registry.get_all_agents()

# Check if an agent is active
is_active = await registry.is_agent_active("agent_id")

# Get an agent's type
agent_type = await registry.get_agent_type("agent_id")
```

### Organization Management

```python
# Register agents with organization info
registration = AgentRegistration(
    agent_id="agent1",
    organization_id="org1",  # Specify organization
    # ... other registration details
)

await registry.register(registration)

# Get agents by organization
agents = await registry.get_agents_by_organization("org1")
```

## Implementation Notes

### Embedding Models

The capability discovery service uses Hugging Face's sentence-transformers for embedding capabilities. By default, it uses the `all-mpnet-base-v2` model, which provides a good balance of accuracy and performance.

### Optional Dependencies

The registry system has optional dependencies for advanced features:

```
# For FAISS vector store
pip install langchain-community faiss-cpu

# For USearch vector store (lighter alternative)
pip install langchain-community usearch 

# For embedding models
pip install langchain-huggingface sentence-transformers
```

The system will gracefully degrade if these dependencies are not available.

### Asynchronous Design

All registry methods are designed to be asynchronous for better performance in web applications and services:

```python
# All methods are async
await registry.register(registration)
await registry.get_by_capability("capability_name")
await registry.get_by_capability_semantic("capability description")
```

### Thread Safety

The registry is designed to be thread-safe for concurrent access in multi-threaded environments.

## Best Practices

1. **Include Detailed Capability Descriptions**: More detailed descriptions lead to better semantic matching
2. **Use Organization IDs**: Group agents by organization for better organization
3. **Adjust Similarity Thresholds**: Tune thresholds based on your specific use case 
4. **Save Vector Stores**: Use `save_vector_store()` in production for faster startup
5. **Handle Asynchronous Methods**: Always use `await` with registry methods
6. **Consider Resource Usage**: Embedding models can use significant memory - use smaller models when needed
7. **Verify Agent Identities**: Always verify agent identities during registration 