# AgentConnect Servers

HTTP server implementations for AgentConnect services.

## Directory Structure

```
servers/
├── __init__.py                     # Package exports
├── registry_api_server.py          # Registry API server implementation
└── README.md                       # This file
```

## Overview

The servers module provides FastAPI-based HTTP servers that expose AgentConnect functionality over REST APIs. Currently implements the Registry API Server, with additional servers planned for future releases.

## Registry API Server

REST API server for agent registry operations - registration, search, and management.

### Quick Start

```bash
# Development
python -m agentconnect.servers.registry_api_server

# With custom port
uvicorn agentconnect.servers.registry_api_server:app --port 8080 --reload
```

**API Docs:** `http://localhost:8000/docs`

### Configuration

Environment variables (see [`agentconnect/core/config.py`](../core/config.py)):

```bash
# API Server
AGENTCONNECT_REGISTRY_API_host=localhost                    # Server host
AGENTCONNECT_REGISTRY_API_port=8000                        # Server port  
AGENTCONNECT_REGISTRY_API_debug=false                      # Debug mode
AGENTCONNECT_REGISTRY_API_allowed_origins='["http://localhost:3000","http://localhost:5173"]' # CORS origins (JSON array)

# Vector Search
AGENTCONNECT_REGISTRY_model_name=sentence-transformers/all-mpnet-base-v2
AGENTCONNECT_REGISTRY_cache_folder=./.cache/huggingface/embeddings
AGENTCONNECT_REGISTRY_vector_store_path=./.cache/vector_stores
AGENTCONNECT_REGISTRY_in_memory=true

# Logging
AGENTCONNECT_level=INFO
AGENTCONNECT_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Core Endpoints

#### Health Check
```bash
GET /health
# Returns: {"status": "healthy", "registry_status": "initialized_and_ready"}
```

#### Agent Registration
```bash
POST /agents/register
Content-Type: application/json

{
  "agent_id": "my_agent_v1",
  "agent_type": "AI",
  "interaction_modes": ["AGENT_TO_AGENT"],
  "identity": {
    "did": "did:key:abc123",
    "public_key": "-----BEGIN PUBLIC KEY-----...",
    "verification_status": "verified"
  },
  "name": "My Agent",
  "summary": "Processes data files",
  "capabilities": [
    {
      "name": "data_processing",
      "description": "Process CSV and JSON files"
    }
  ],
  "tags": ["data", "processing"],
  ...
}
```

#### Agent Search
```bash
POST /agents/search/semantic
Content-Type: application/json

{
  "query": "process data files",
  "top_k": 5,
  "strictness": 0.3,
  "output_detail": "summary"
}
```

#### Agent Management
```bash
GET /agents/{agent_id}                # Get agent details
GET /agents                           # All agents
PUT /agents/{agent_id}                # Update agent
DELETE /agents/{agent_id}             # Unregister agent
```

### Complete API Reference

For all available endpoints and detailed schemas:
- **Interactive Docs:** `/docs` when server is running
- **Registry Core:** [`agentconnect/core/registry/README.md`](../core/registry/README.md)
- **Agent Types:** [`agentconnect/core/types.py`](../core/types.py)
- **Search Schemas:** [`agentconnect/core/registry/search/schemas.py`](../core/registry/search/schemas.py)

### Production Deployment

```bash
# With Gunicorn
gunicorn agentconnect.servers.registry_api_server:app -w 4 -k uvicorn.workers.UvicornWorker

# With environment config
HOST=0.0.0.0 PORT=8000 python -m agentconnect.servers.registry_api_server
```

## Future Servers

Additional server implementations will be added to this module:
- Communication Server (agent messaging)
- Task Server (distributed task management)
- Gateway Server (API gateway with auth)
