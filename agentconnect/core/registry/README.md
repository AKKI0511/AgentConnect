# AgentConnect Registry

The Registry subsystem manages agent information, discovery, and identity verification using direct indexing and Qdrant-powered semantic search.

## Directory Structure

```
registry/
├── __init__.py                     # Package exports
├── capability_discovery_impl/      # Implementation details for semantic search
├── registry_base.py                # AgentRegistry class
├── capability_discovery.py         # CapabilityDiscoveryService 
├── identity_verification.py        # Identity verification functions
├── registration.py                 # AgentRegistration dataclass
└── README.md                       # This file
```

## Core Components

### AgentRegistry

Single source of truth for agent registration and discovery:

- Register and unregister agents
- Find agents by capability name or semantic description
- Filter agents by organization, developer, interaction mode etc.
- Verify agent identities

### CapabilityDiscoveryService

Provides semantic search using vector embeddings and Qdrant:

- Finds agents by capability descriptions rather than just exact name matches
- Supports metadata filtering (tags, input/output modes, etc.)
- Falls back to simpler search when vector search unavailable

### AgentRegistration

Stores agent data including identity, capabilities, skills, metadata, and configuration.

Main fields include `agent_id`, `agent_type`, `interaction_modes`, `identity`, `name`, `capabilities`, `skills`, `tags`, and `developer` among others.

## Configuration

Configure the registry with a simple dictionary:

```python
config = {
    # For testing or simple usage
    "in_memory": True,                  # No external server needed
    
    # For production (examples)
    # "path": "./local_qdrant_db",     # Local file storage
    # "url": "http://localhost:6333",  # Remote Qdrant server
    # "url": "https://xyz-example.us-east.aws.cloud.qdrant.io", # Qdrant Cloud
    # "api_key": "your-qdrant-api-key", # For Qdrant Cloud or secured instances
    
    # Optional settings
    "model_name": "sentence-transformers/all-mpnet-base-v2",  # Default embedding model
    "timeout": 30,                      # Client timeout for remote connections
    "use_quantization": True,           # Storage reduction
    "batch_size": 100                   # For indexing operations
}

registry = AgentRegistry(vector_search_config=config)
```

> **Important:** When not using `in_memory` mode, you must have a Qdrant server running:
> - For `url` option: You need a Qdrant server running at the specified URL (Docker container or cloud instance)
> - For Qdrant Cloud: Create an account at [Qdrant Cloud](https://qdrant.tech/), set up a cluster, and use the provided URL and API key
> - For local Docker deployment: `docker run -p 6333:6333 qdrant/qdrant`
>
> See the [official Qdrant documentation](https://qdrant.tech/documentation/) for detailed setup instructions.

## Basic Usage

```python
import asyncio
from agentconnect.core.registry import AgentRegistry, AgentRegistration
from agentconnect.core.types import AgentIdentity, AgentType, Capability, InteractionMode

async def main():
    # Initialize registry
    registry = AgentRegistry(vector_search_config={"in_memory": True})
    await registry.ensure_initialized()  # Wait for initialization (Generally not needed as it's handled internally)
    
    # Create and register an agent
    agent = AgentRegistration(
        agent_id="math_bot_001",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        identity=AgentIdentity.create_key_based(),
        name="MathBot",
        capabilities=[
            Capability(name="addition", description="Adds numbers together")
        ],
        tags=["math"]
    )
    
    await registry.register(agent)
    
    # Find by exact capability name
    exact_matches = await registry.get_by_capability("addition")
    
    # Find by semantic description
    semantic_results = await registry.get_by_capability_semantic(
        capability_description="agent that can sum numbers",
        filters={"tags": ["math"]}  # Optional filtering
    )
    
    # Check results
    for agent_reg, score in semantic_results:
        print(f"{agent_reg.name}: {score:.2f}")
    
    # Unregister when done
    await registry.unregister("math_bot_001")

if __name__ == "__main__":
    asyncio.run(main())
```

## Dependencies

For semantic search functionality:
```bash
pip install qdrant-client langchain-huggingface sentence-transformers numpy
```

## Important Notes

- All registry methods are asynchronous - use `await` with them
- Call `await registry.ensure_initialized()` after creating the registry (Generally not needed as it's handled internally)
- Provide detailed descriptions in capabilities for better semantic search
- If using a remote Qdrant server (`url` option), ensure the server is running before initialization
- For production use, consider using Qdrant Cloud or a self-hosted Qdrant server with proper security
- See [Capability Discovery Implementation](capability_discovery_impl/README.md) for advanced details 