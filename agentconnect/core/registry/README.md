# AgentConnect Registry

The Registry subsystem manages agent information, discovery, and identity verification using direct indexing and Qdrant-powered semantic search.

## Directory Structure

```
registry/
├── __init__.py                     # Package exports
├── capability_discovery_impl/      # Implementation details for semantic search
├── search/                         # Search interface schemas and utilities
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

### Search Interface

The `search/` subdirectory provides standardized schemas and utilities for agent search operations across all AgentConnect interfaces. It serves as the interface layer between the registry domain and external consumers (API servers, MCP servers, LangChain tools, etc.).

See [Search Module Documentation](search/README.md) for detailed information about search schemas, utilities, and usage patterns.

## Configuration

Use the SDK YAML configuration (`agentconnect.yaml`) for the registry component.

Example `agentconnect.yaml` snippet for `registry.vector_search`:

```yaml
registry:
  vector_search:
    model_name: "sentence-transformers/all-mpnet-base-v2"
    cache_folder: "./.cache/huggingface/embeddings"
    vector_store_path: "./.cache/vector_stores"
    deployment:
      type: "in_memory"             # or "local_file" / "remote"
      # path: "./local_qdrant_db"   # if local_file
      # url: "http://localhost:6333" # if remote
    advanced:
      timeout: 30
      prefer_grpc: false
      grpc_port: null
      use_quantization: true
      vectors_on_disk: false
      index_on_disk: false
      batch_size: 100
```

- For remote deployments, the Qdrant API key is read from the `QDRANT_API_KEY` environment variable.
- Server deployment uses environment variables only; see [AgentConnect Servers](../../servers/README.md).

Python usage examples:

```python
from agentconnect.config import settings
from agentconnect.core.registry import AgentRegistry
from agentconnect.config.models import VectorSearchSettings

# 1) Use settings populated from agentconnect.yaml
registry = AgentRegistry(vector_search_config=settings.registry.vector_search)

# 2) Or pass a VectorSearchSettings instance
custom_settings = VectorSearchSettings(
    model_name="sentence-transformers/all-mpnet-base-v2",
    deployment={"type": "in_memory"},
)
registry2 = AgentRegistry(vector_search_config=custom_settings)

# 3) Optional dict override (must match Pydantic shape)
override = {
    "model_name": "sentence-transformers/all-mpnet-base-v2",
    "deployment": {"type": "remote", "url": "http://localhost:6333"},
    "advanced": {"timeout": 30, "batch_size": 100}
}
registry3 = AgentRegistry(vector_search_config=override)
```

> When not using `in_memory` mode, you must have a Qdrant server running:
> - For `deployment.type: remote`: Ensure a Qdrant server is reachable at the configured `url` (Docker, self-hosted, or Qdrant Cloud)
> - For [Qdrant Cloud](https://qdrant.tech/): Create a cluster, set `url`, and set `QDRANT_API_KEY` in your environment
> - For local Docker: `docker run -p 6333:6333 qdrant/qdrant`
>
> See the [official Qdrant documentation](https://qdrant.tech/documentation/) for detailed setup.

## Basic Usage

```python
import asyncio
from agentconnect.core.registry import AgentRegistry, AgentRegistration
from agentconnect.core.types import AgentIdentity, AgentType, Capability, InteractionMode

async def main():
    # Initialize registry (default config)
    registry = AgentRegistry()
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