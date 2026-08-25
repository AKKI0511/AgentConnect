# AgentConnect Clients

The Clients subsystem provides programmatic interfaces for interacting with AgentConnect services, offering both low-level API access and high-level abstractions.

## Directory Structure

```
index/
├── __init__.py                 # Package exports
├── client.py                   # Registry API client implementation
└── CLIENT.md                   # This file
```

## Overview

The clients module contains HTTP-based clients that communicate with AgentConnect servers, enabling remote access to registry functionality, agent management, and distributed agent discovery.

## Core Components

### RegistryAPIClient

> **Note:** The `RegistryAPIClient` is currently not thread-safe. Consider creating separate client instances for each thread. This will be addressed in future releases.

**File:** `client.py`

A comprehensive HTTP client for interacting with the AgentConnect Registry API Server. This client mirrors the interface of the local `AgentRegistry` class but operates over HTTP/REST APIs.

#### Key Features

- **Full Registry Interface:** Mirrors all `AgentRegistry` methods for seamless local-to-remote migration
- **Connection Management:** Built-in connection pooling, timeouts, and retry logic
- **Error Handling:** Comprehensive error handling with exponential backoff retry
- **Type Safety:** Full Pydantic model validation for request/response data
- **Async/Await:** Non-blocking operations with proper resource cleanup

#### Configuration

```python
from agentconnect.index import RegistryAPIClient

# Basic usage - auto-detects server from settings.clients.registry.base_url
client = RegistryAPIClient()

# Custom configuration
client = RegistryAPIClient(
    base_url="http://localhost:8000",
    timeout=30.0,
    connect_timeout=10.0,
    read_timeout=30.0,
    max_connections=10,
    max_keepalive_connections=5
)
```

#### Core Methods

##### Agent Management
- `register(registration: AgentRegistration) -> bool`
- `unregister(agent_id: str) -> bool`
- `get_registration(agent_id: str) -> Optional[AgentRegistration]`
- `get_all_agents() -> List[AgentRegistration]`
- `update_registration(agent_id: str, updates: Dict[str, Any]) -> Optional[AgentRegistration]`

##### Agent Discovery
- `get_by_capability_semantic(capability_description: str, limit: int = 10, similarity_threshold: float = 0.1, filters: Optional[Dict[str, List[str]]] = None) -> List[Tuple[AgentRegistration, float]]`
- `get_by_capability(capability_name: str, limit: int = 10, similarity_threshold: float = 0.1) -> List[AgentRegistration]`
- `get_all_capabilities() -> List[str]`

##### Agent Properties
- `get_agent_type(agent_id: str) -> Optional[AgentType]`
- `get_by_interaction_mode(mode: InteractionMode) -> List[AgentRegistration]`
- `get_by_organization(organization: str) -> List[AgentRegistration]`
- `get_verified_agents() -> List[AgentRegistration]`
- `get_by_owner(owner_id: str) -> List[AgentRegistration]`

##### Identity & Verification
- `verify_agent(agent_id: str) -> bool`
- `verify_owner(agent_id: str, owner_id: str) -> bool`

#### Usage Examples

##### Basic Agent Registration

```python
import asyncio
from agentconnect.index import RegistryAPIClient
from agentconnect.team.directory import AgentRegistration
from agentconnect.core import AgentType, InteractionMode, AgentIdentity, Capability

async def register_agent_example():
    async with RegistryAPIClient() as client:
        # Create agent registration
        agent = AgentRegistration(
            agent_id="data_processor_v1",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=AgentIdentity.create_key_based(),
            name="Data Processor",
            summary="Processes CSV and JSON data files",
            capabilities=[
                Capability(name="csv_processing", description="Parse and transform CSV files"),
                Capability(name="json_processing", description="Parse and transform JSON data")
            ],
            tags=["data", "processing", "csv", "json"]
        )
        
        # Register agent
        success = await client.register(agent)
        if success:
            print(f"Successfully registered {agent.agent_id}")
        else:
            print("Registration failed")

# Run the example
asyncio.run(register_agent_example())
```

##### Semantic Agent Discovery

```python
async def discover_agents_example():
    async with RegistryAPIClient() as client:
        
        # Find agents using semantic search
        results = await client.get_by_capability_semantic(
            capability_description="process data files and generate reports",
            limit=5,
            similarity_threshold=0.3,
            filters={"tags": ["data", "reporting"]}
        )
        
        # Process results
        for agent_reg, score in results:
            print(f"Found: {agent_reg.name} (Score: {score:.3f})")
            print(f"  Capabilities: {[cap.name for cap in agent_reg.capabilities]}")
            print(f"  Tags: {agent_reg.tags}")

asyncio.run(discover_agents_example())
```

##### Bulk Operations

```python
async def bulk_operations_example():
    async with RegistryAPIClient() as client:
        
        # Get all agents from a specific organization
        org_agents = await client.get_by_organization("acme_corp")
        print(f"Found {len(org_agents)} agents from Acme Corp")
        
        # Get all verified agents
        verified = await client.get_verified_agents()
        print(f"Found {len(verified)} verified agents")
        
        # Get agents by interaction mode
        api_agents = await client.get_by_interaction_mode(InteractionMode.AGENT_TO_AGENT)
        print(f"Found {len(api_agents)} A2A agents")

asyncio.run(bulk_operations_example())
```

#### Error Handling

The client includes comprehensive error handling:

```python
async def error_handling_example():
    try:
        async with RegistryAPIClient() as client:
            
            # This will automatically retry on network errors
            result = await client.get_registration("some_agent_id")
            
            if result is None:
                print("Agent not found (404)")
            else:
                print(f"Found agent: {result.name}")
                
    except httpx.RequestError as e:
        print(f"Network error after all retries: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(error_handling_example())
```

#### Connection Management

##### Context Manager (Recommended)

```python
# Automatic resource cleanup
async with RegistryAPIClient() as client:
    # ... perform operations ...
# Client is automatically closed
```

##### Manual Management

```python
client = RegistryAPIClient()
try:
    # ... perform operations ...
finally:
    await client.close()  # Important: clean up resources
```

#### Configuration Settings

The client uses `settings` from `agentconnect.config` and can be configured via `agentconnect.yaml`:

```python
# Client configuration (available via settings.clients.registry)
settings.clients.registry.base_url                    # Default: "http://localhost:8000"
settings.clients.registry.default_timeout             # Default: 30.0
settings.clients.registry.connect_timeout             # Default: 10.0
settings.clients.registry.read_timeout                # Default: 30.0
settings.clients.registry.pool_timeout                # Default: 5.0
settings.clients.registry.max_retries                 # Default: 3
settings.clients.registry.retry_backoff_factor        # Default: 0.5
settings.clients.registry.retryable_status_codes      # Default: [502, 503, 504]
settings.clients.registry.max_connections             # Default: 10
settings.clients.registry.max_keepalive_connections   # Default: 5
```

Example `agentconnect.yaml` configuration:

```yaml
clients:
  registry:
    base_url: "http://production-registry:8000"
    default_timeout: 60.0
    max_retries: 5
    max_connections: 20
```

**Note:** Server configuration is separate and uses environment variables with the `AGENTCONNECT_REGISTRY_` prefix for infrastructure deployment.

#### Dependencies

```bash
# Required packages
poetry add httpx pydantic
```

#### Best Practices

1. **Use Context Managers:** Always use `async with` for automatic resource cleanup
2. **Handle Errors:** Implement proper error handling for network failures
3. **Connection Reuse:** Reuse client instances when possible to benefit from connection pooling
4. **Timeout Configuration:** Set appropriate timeouts based on your network environment
5. **Graceful Degradation:** Have fallback strategies for when the API server is unavailable

## Testing

### Unit Tests

```bash
# Run client tests
poetry run pytest tests/index/ -v
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure the Registry API server is running
   - Check host/port configuration
   - Verify network connectivity

2. **Timeout Errors**
   - Increase timeout values
   - Check server performance
   - Consider retry configuration

3. **Authentication Errors**
   - Verify Registry API server is properly configured (check environment variables with `AGENTCONNECT_REGISTRY_` prefix)
   - Check CORS settings for web clients

4. **Serialization Errors**
   - Ensure compatible versions of Pydantic models
   - Check data types in request payloads

### Debug Mode

Enable debug logging for detailed HTTP request/response information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Will show detailed HTTP logs
client = RegistryAPIClient()
```

## Future Extensions

The clients module is designed for expansion with additional service clients:

- **Communication Client:** For agent-to-agent messaging
- **Task Client:** For distributed task management
- **Monitoring Client:** For system health and metrics
- **Payment Client:** For agent payment processing

## Performance Considerations & Future Optimizations

### Current N+1 Query Issue in API Client

**Problem:** The `RegistryAPIClient.get_by_capability_semantic()` method currently exhibits an N+1 query pattern:
1. One API call to `/agents/search/semantic` (returns `AgentSearchResultItem`)
2. N additional API calls to `/agents/{agent_id}` (to get complete `AgentRegistration` data)

This happens because `AgentSearchResultItem` lacks critical fields required by `AgentRegistration`:
- `identity` (AgentIdentity) - Cannot be fabricated due to security implications
- `agent_type` (required field)
- `interaction_modes` (required field)
- `registered_at` (required field)

**Current Status:** Accepted as temporary trade-off to maintain data integrity and security.

### Future Optimization Strategies

#### Option 1: Enhanced Search Endpoint (Recommended)
**Target:** `agentconnect/index/registry_api_server.py`

Create a new endpoint `/agents/search/semantic-full` that returns complete `AgentRegistration` objects instead of `AgentSearchResultItem`:

```python
@app.post(
    "/agents/search/semantic-full",
    response_model=List[AgentRegistration],  # Return full objects
    summary="Search agents by semantic capability (full registration data)",
    tags=["Agent Search"],
)
async def search_agents_semantic_full_endpoint(
    search_input: AgentSearchInput,
) -> List[AgentRegistration]:
    registry = get_registry()
    # ... implementation similar to current endpoint but returns full AgentRegistration objects
```

**Benefits:**
- Single API call eliminates N+1 queries
- Maintains complete data integrity
- Backward compatible (keeps existing endpoint)

#### Option 2: Batch Fetch Endpoint
**Target:** `agentconnect/index/registry_api_server.py`

Create a bulk fetch endpoint for multiple agent IDs:

```python
@app.post(
    "/agents/batch",
    response_model=List[AgentRegistration],
    summary="Get multiple agents by ID in single request",
    tags=["Agents"],
)
async def get_agents_batch_endpoint(
    agent_ids: List[str]
) -> List[AgentRegistration]:
    # Fetch multiple agents in single call
```

**Benefits:**
- Reduces N calls to 1 call
- Reusable for other bulk operations
- Minimal changes to existing client logic

#### Option 3: Enhanced Schema (Breaking Change)
**Target:** `agentconnect/team/directory/search/schemas.py`

Extend `AgentSearchResultItem` to include all critical fields from `AgentRegistration`:

```python
class AgentSearchResultItem(BaseModel):
    # ... existing fields ...
    
    # Add missing critical fields
    agent_type: Optional[AgentType] = None
    interaction_modes: Optional[List[InteractionMode]] = None
    identity: Optional[AgentIdentity] = None  # Include complete identity
    registered_at: Optional[datetime] = None
```

**Considerations:**
- Breaking change requiring updates across all consumers
- Larger response payloads
- Requires careful migration strategy

### Implementation Priority

1. **Immediate (Low Risk):** Option 1 - New enhanced endpoint
2. **Medium Term:** Option 2 - Batch fetch endpoint for other use cases
3. **Long Term:** Option 3 - Schema enhancement after careful impact analysis

### Related Files

- **Client:** `agentconnect/index/client.py` - Lines 278-403 (N+1 pattern)
- **Server:** `agentconnect/index/registry_api_server.py` - Lines 257-296 (semantic search endpoint)
- **Schemas:** `agentconnect/team/directory/search/schemas.py` - AgentSearchResultItem definition
- **Utils:** `agentconnect/team/directory/search/utils.py` - populate_search_result_item function
