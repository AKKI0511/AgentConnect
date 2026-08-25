## AgentConnect SDK Configuration

SDK configuration for agent developers: define `agentconnect.yaml` and optional runtime overrides; servers are configured separately via environment variables in [AgentConnect Servers](../index/README.md).

> Important: SDK uses YAML (loaded into `agentconnect.config.settings`). Servers are env-only and do not read YAML. Keep developer (YAML) and operator (env) configuration separate.

## Configuration Precedence

- Runtime kwargs > agentconnect.yaml > model defaults (Pydantic).
- Environment variables are not read by the global SDK settings. They are reserved for secrets used by subsystems (for example: `QDRANT_API_KEY`, `CDP_API_KEY_NAME`, `CDP_API_KEY_PRIVATE_KEY`) and for server configuration in `agentconnect/index/`.

## How to Use

- Import `settings` and access nested models:

```python
from agentconnect.config import settings

registry_cfg = settings.registry.vector_search
base_url = settings.clients.registry.base_url
```

- Override via `load_settings(...)` when needed:

```python
from agentconnect.config import load_settings

custom = load_settings(registry={"vector_search": {"deployment": {"type": "in_memory"}}})
```

- `AgentConnectSettings` to create a settings object:

```python
from agentconnect.config import AgentConnectSettings

settings = AgentConnectSettings(project_name="My Project")
```

- CLI:

```bash
agentconnect config init|show|validate <file>
```

> Note: `config show` redacts secrets (SecretStr) and prints YAML if PyYAML is present, otherwise JSON.

## Settings Overview

- **AgentConnectSettings**
  - Fields: `project_name`, `registry`, `communication`, `clients`, `mcp`, `payments`.
  - No debug/logging fields in global settings.

- **RegistrySettings**
  - `vector_search`: `VectorSearchSettings`.

- **VectorSearchSettings**
  - Essential: `model_name`, `cache_folder`, `vector_store_path`.
  - Deployment (choose one):
    - `in_memory`
    - `local_file` (fields: `path`)
    - `remote` (fields: `url`, `api_key` via `QDRANT_API_KEY` env; `api_key` is `SecretStr` and redacted in outputs)
  - Advanced: `timeout`, `grpc_port`, `prefer_grpc`, `use_quantization`, `vectors_on_disk`, `index_on_disk`, `batch_size`.

- **CommunicationSettings**
  - `enable_message_history`.

- **ClientSettings**
  - `registry`: `RegistryClientSettings` with:
    - `base_url`
    - Timeouts: `default_timeout`, `connect_timeout`, `read_timeout`, `pool_timeout`
    - Retries: `max_retries`, `retry_backoff_factor`, `retryable_status_codes`
    - Connection pool: `max_connections`, `max_keepalive_connections`

- **MCPSettings**
  - `agent_discovery`: `MCPAgentDiscoverySettings` with `enabled`, `top_k`, `strictness`, `output_detail` (`minimal|summary|capabilities|full`).

- **PaymentsSettings**
  - `default_token_symbol` (normalized to uppercase; drives ERC-20 vs native)
  - `wallet_data_dir` (non-secret path for wallets)
  - Note: CDP keys are env-only (`CDP_API_KEY_NAME`, `CDP_API_KEY_PRIVATE_KEY`). No network id in YAML.

## Example agentconnect.yaml

Create an `agentconnect.yaml` file in your project root, or copy the example file from `agentconnect/config/agentconnect.example.yaml`:

```bash
cp agentconnect/config/agentconnect.example.yaml agentconnect.yaml
```

```yaml
# AgentConnect Configuration
project_name: "AgentConnect"

registry:
  vector_search:
    model_name: "sentence-transformers/all-mpnet-base-v2"
    cache_folder: "./.cache/huggingface/embeddings"
    vector_store_path: "./.cache/vector_stores"

    # Deployment mode (exactly one)
    deployment:
      type: "in_memory"  # "local_file" or "remote" also supported
      # For local_file: path: "./local_qdrant_db"
      # For remote: url: "http://localhost:6333" (API key via QDRANT_API_KEY)

    # Advanced tuning (optional)
    advanced:
      timeout: 30
      grpc_port: null
      prefer_grpc: false
      use_quantization: true
      vectors_on_disk: false
      index_on_disk: false
      batch_size: 100

payments:
  default_token_symbol: "USDC"
  wallet_data_dir: "data/agent_wallets"

communication:
  enable_message_history: true

clients:
  registry:
    base_url: "http://localhost:8000"

mcp:
  agent_discovery:
    enabled: true
    top_k: 5
    strictness: 0.2
    output_detail: "summary"  # minimal | summary | capabilities | full
```

## Secrets & Redaction

- Use environment variables for secrets (for example: `QDRANT_API_KEY`, `CDP_API_KEY_NAME`). Do not place secrets in YAML.
- `settings.model_dump_yaml_safe()` redacts any `SecretStr` fields (e.g., remote Qdrant `api_key`) in outputs and CLI.

## CLI Integration

Generate and manage configuration via the CLI:

```bash
# Prompts before overwriting an existing `agentconnect.yaml`
agentconnect config init

# redacts secrets; YAML if PyYAML available, else JSON
agentconnect config show

# validates your configuration file
agentconnect config validate agentconnect.yaml
```

Note: CLI commands re-read configuration fresh each run using `load_settings()` to reflect the latest `agentconnect.yaml`. Library code commonly imports a process-level snapshot via `from agentconnect.config import settings` for convenience.

## Dependencies

- `pydantic` (required)
- `PyYAML` (optional, for YAML pretty-print and CLI)
- SDK config does not depend on `pydantic-settings`; servers do (see [AgentConnect Servers](../index/README.md)).


## Related Documentation

- **Server Deployment**: See [AgentConnect Servers](../index/README.md) for deploying registry infrastructure
- **Core Registry**: See [AgentConnect Core Registry](../team/directory/README.md) for registry functionality
- **Agent Development**: See main documentation for building agents with AgentConnect
