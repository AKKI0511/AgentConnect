# AgentConnect Servers

Standalone HTTP server implementations for AgentConnect services. This guide is for **System Operators** deploying and managing AgentConnect infrastructure.

## Overview

The servers module provides FastAPI-based HTTP services that expose AgentConnect functionality over REST APIs. All servers operate as standalone applications configured **exclusively via environment variables**.

## Directory Structure

```
servers/
├── __init__.py                     # Package exports
├── config.py                       # Server configuration models
├── registry_api_server.py          # Registry API server implementation
├── docker-compose.example.yml      # Minimal Compose example (env_file: .env)
├── k8s/
│   └── deployment.example.yaml     # Minimal Kubernetes deployment (envFrom)
└── README.md                       # This file
```

## Available Servers

### Registry API Server

REST API server for agent registry operations - registration, search, and management.

**Purpose**: Agent discovery and capability matching  
**Environment Prefix**: `AGENTCONNECT_REGISTRY_`

## General Architecture

All AgentConnect servers follow consistent patterns:

### Configuration Strategy
- **Environment variables only** - No configuration files for servers (no YAML)
- **Prefixed variables** - Each server uses a unique `AGENTCONNECT_<SERVER>_` prefix
- **.env support for local dev** - `.env` is read automatically for developer convenience
- **Secrets** - Sensitive values like `QDRANT_API_KEY` are read directly from env (never embed in JSON)
- **Validation** - All configuration validated using Pydantic models

### Deployment Patterns
- **Standalone operation** - Each server can run independently
- **Docker ready** - Containerized deployment support
- **Health checks** - Standard `/health` endpoints
- **Structured logging** - consistent formatting
- **Graceful shutdown** - Proper cleanup on termination

## Quick Start

### Registry API Server

```bash
# Run with default settings (development)
agentconnect serve registry
```

Developer note (for contributors): You can also run via uvicorn or module path: `uvicorn agentconnect.servers.registry_api_server:app` or `python -m agentconnect.servers.registry_api_server`.

The server will be available at `http://localhost:8000` with interactive API documentation at `/docs`.

You can configure the server using environment variables only. No `agentconnect.yaml` is read by servers.

### Programmatic usage

You can construct the FastAPI app with custom settings without using environment variables:

```python
from agentconnect.servers.config import RegistryAPISettings
from agentconnect.servers.registry_api_server import create_registry_api_app

custom = RegistryAPISettings(
    host="0.0.0.0",
    port=8000,
    log_level="DEBUG",
)
app = create_registry_api_app(custom)

# Optionally run with Uvicorn programmatically
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=custom.host, port=custom.port, log_level=custom.log_level.lower())
```

Preferred CLI:

```bash
agentconnect serve registry
```

### .env quickstart

For local development with env files:

```bash
# Copy the server sample .env to the working directory
cp agentconnect/servers/.env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item 'agentconnect/servers/.env.example' '.env'
```

Then run:

```bash
agentconnect serve registry
```

## Configuration Reference

All servers use environment variables with server-specific prefixes to avoid conflicts.

### Registry API Server (`AGENTCONNECT_REGISTRY_`)

Core server settings (env-only):

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENTCONNECT_REGISTRY_HOST` | string | `localhost` | Server host address |
| `AGENTCONNECT_REGISTRY_PORT` | int | `8000` | Server port (1-65535) |
| `AGENTCONNECT_REGISTRY_RELOAD` | bool | `false` | Enable auto-reload (development) |
| `AGENTCONNECT_REGISTRY_LOG_LEVEL` | string | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS` | JSON array or CSV | `[`"http://localhost:5173"`, `"http://localhost:3000"`]` | CORS allowed origins (JSON preferred; CSV accepted) |

Vector search configuration (nested with `__` or single JSON override):

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__MODEL_NAME` | string | `sentence-transformers/all-mpnet-base-v2` | Embedding model |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__CACHE_FOLDER` | string | `./.cache/huggingface/embeddings` | Embedding cache directory |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__VECTOR_STORE_PATH` | string | `./.cache/vector_stores` | Local vector store temporary path |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE` | string | `in_memory` | Deployment mode: `in_memory`, `local_file`, `remote` |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__PATH` | string | `./local_qdrant_db` | Local storage path (local_file mode) |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL` | string | - | Remote Qdrant URL (remote mode) |
| `QDRANT_API_KEY` | string | - | Qdrant API key (remote mode) |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__TIMEOUT` | int | `30` | Qdrant client timeout (seconds) |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__GRPC_PORT` | int | - | Qdrant gRPC port (remote deployments) |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__PREFER_GRPC` | bool | `false` | Prefer gRPC over HTTP |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__USE_QUANTIZATION` | bool | `true` | Enable INT8 vector quantization |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__VECTORS_ON_DISK` | bool | `false` | Store vectors on disk |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__INDEX_ON_DISK` | bool | `false` | Store index on disk |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__BATCH_SIZE` | int | `100` | Indexing batch size |
| `AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON` | JSON | - | Single-var JSON override for entire `vector_search` block (highest precedence) |

Note: `QDRANT_API_KEY` is read directly from the environment by the vector component. Do not include secrets in JSON.

## Deployment Examples

### Use a single .env file (recommended)

All servers auto-load a `.env` in the working directory via Pydantic BaseSettings (`env_file=".env"`). Use one `.env` for local, Docker, Compose, and Kubernetes.

- Copy the example and run locally (app auto-loads `.env`):

  ```bash
  cp agentconnect/servers/.env.example .env
  agentconnect serve registry
  ```

  PowerShell:

  ```powershell
  Copy-Item 'agentconnect/servers/.env.example' '.env'
  agentconnect serve registry
  ```

- Docker: pass the same file with `--env-file` (works on Windows/macOS/Linux; `.env` must exist on host):

  ```bash
  docker run -p 8000:8000 --env-file ./.env agentconnect/registry-server:latest
  ```

- Docker Compose: reference the file with `env_file: .env` (copy `agentconnect/servers/.env.example` → `.env` first). See `agentconnect/servers/docker-compose.example.yml` for a complete minimal example.

  ```yaml
  version: '3.8'
  services:
    registry:
      image: agentconnect/registry-server:latest
      ports:
        - "8000:8000"
      env_file:
        - .env
  ```

- Kubernetes: create a ConfigMap from the `.env` and a Secret for sensitive keys, then load both via `envFrom` (do not commit secrets to VCS):

  ```bash
  kubectl create configmap agentconnect-registry --from-env-file=.env
  kubectl create secret generic qdrant-secrets --from-literal=QDRANT_API_KEY=REPLACE_ME
  ```

  Deployment snippet (see `agentconnect/servers/k8s/deployment.example.yaml`):

  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: agentconnect-registry
  spec:
    replicas: 1
    selector:
      matchLabels:
        app: agentconnect-registry
    template:
      metadata:
        labels:
          app: agentconnect-registry
      spec:
        containers:
        - name: registry
          image: agentconnect/registry-server:latest
          ports:
          - containerPort: 8000
          envFrom:
          - configMapRef:
              name: agentconnect-registry
          - secretRef:
              name: qdrant-secrets
  ```

Cross-OS note: `.env` parsing rules shown above work the same on Linux/macOS/Windows.

Example `.env` contents:

```bash
# .env (example)
AGENTCONNECT_REGISTRY_HOST=localhost
AGENTCONNECT_REGISTRY_PORT=8000
AGENTCONNECT_REGISTRY_LOG_LEVEL=DEBUG
# Preferred JSON format
AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS='["http://localhost:5173","http://localhost:3000"]'
# Alternatively, CSV format (convenience)
# AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Nested env with double underscores
AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE=remote
AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL=https://qdrant.example.com:6333
AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__TIMEOUT=60

# Or single-var JSON override (highest precedence)
AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON='{"deployment":{"type":"remote","url":"https://qdrant.example.com:6333"},"advanced":{"timeout":60}}'
```

The sections below show per-variable examples as an alternative or for overrides.

### Using Docker

Individual server container:

```bash
docker run -p 8000:8000 \
  -e AGENTCONNECT_REGISTRY_HOST=0.0.0.0 \
  -e AGENTCONNECT_REGISTRY_LOG_LEVEL=INFO \
  -e AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS='["http://localhost:5173","http://localhost:3000"]' \
  -e AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE=remote \
  -e AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL=https://qdrant.example.com:6333 \
  agentconnect/registry-server:latest
```

### Docker Compose

Multi-server deployment:

```yaml
version: '3.8'

services:
  registry:
    image: agentconnect/registry-server:latest
    ports:
      - "8000:8000"
    environment:
      AGENTCONNECT_REGISTRY_HOST: 0.0.0.0
      AGENTCONNECT_REGISTRY_LOG_LEVEL: INFO
      AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS: '["http://localhost:5173","http://localhost:3000"]'
      AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE: remote
      AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL: http://qdrant:6333
    depends_on:
      - qdrant

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

### Windows PowerShell examples

Set for current session:

```powershell
$env:AGENTCONNECT_REGISTRY_LOG_LEVEL = "DEBUG"
$env:AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS = '["http://localhost:5173","http://localhost:3000"]'  # JSON (preferred)
# Or CSV (convenience)
# $env:AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS = 'http://localhost:5173,http://localhost:3000'
$env:AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE = "remote"
$env:AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL = "https://qdrant.example.com:6333"
```

Persist for user (new sessions):

```powershell
setx AGENTCONNECT_REGISTRY_LOG_LEVEL "INFO"
setx AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON '{"deployment":{"type":"remote","url":"https://qdrant.example.com:6333"}}'
```

### Linux/macOS examples

```bash
export AGENTCONNECT_REGISTRY_LOG_LEVEL=INFO
export AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS='["http://localhost:5173","http://localhost:3000"]'  # JSON (preferred)
# Or CSV (convenience)
# export AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
export AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE=remote
export AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL=https://qdrant.example.com:6333
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentconnect-registry
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentconnect-registry
  template:
    metadata:
      labels:
        app: agentconnect-registry
    spec:
      containers:
      - name: registry
        image: agentconnect/registry-server:latest
        ports:
        - containerPort: 8000
        env:
        - name: AGENTCONNECT_REGISTRY_HOST
          value: "0.0.0.0"
        - name: AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE
          value: "remote"
        - name: AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL
          value: "http://qdrant-service:6333"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

## Monitoring and Observability

All servers provide consistent monitoring capabilities:

### Health Checks
- `GET /health`: Returns 200 if server is running and ready to serve requests

### Logging
- Registry lifecycle logs are emitted via `uvicorn.error.agentconnect.registry` so they always flow through Uvicorn’s handlers.
- Control our registry logger level with `AGENTCONNECT_REGISTRY_LOG_LEVEL` (applied during lifespan startup).
- Control Uvicorn’s own logs via CLI flags (e.g., `--log-level`) or programmatic `uvicorn.run(..., log_level=...)`.

Examples:

```bash
# CLI (env controls our logger; uvicorn log level via run)
agentconnect serve registry

# Windows PowerShell: set our logger level
$env:AGENTCONNECT_REGISTRY_LOG_LEVEL = "DEBUG"
agentconnect serve registry
```

## Troubleshooting

### Common Issues

**Server won't start:**
- Check if port is already in use: `netstat -tulpn | grep :<port>`
- Verify environment variables are properly set
- Check server logs for specific error messages

### Health and Troubleshooting
- Health endpoint: `GET /health`
- If server won't start:
  - Ensure port is free
  - Verify env variables (nested use `__`)
  - For complex settings, prefer `AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON`


## API Documentation

Each server provides interactive API documentation when running:

- **Registry Server**: `http://localhost:8000/docs`

For detailed API schemas, client libraries, and integration examples, see the main AgentConnect documentation.

## Related Documentation

- **SDK Configuration**: See `agentconnect/config/README.md` for agent developer configuration
- **Core Components**: See `agentconnect/core/` for underlying functionality
- **Client Libraries**: See `agentconnect/clients/` for programmatic access
- **Agent Development**: See main documentation for building agents
