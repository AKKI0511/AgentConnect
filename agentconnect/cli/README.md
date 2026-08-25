# AgentConnect CLI

Command line interface for AgentConnect.

## Installation

The CLI is installed with the `agentconnect` package and exposes the `agentconnect` console script.

## Global Usage

```bash
agentconnect --help
```

## Commands and Options

### version

Print the installed AgentConnect version.

```bash
agentconnect version
```

### config

Manage SDK configuration (`agentconnect.yaml`).

```bash
agentconnect config --help
```

- init
  - Purpose: Generate `agentconnect.yaml` in the current directory.
  - Flags:
    - `--force` Overwrite existing `agentconnect.yaml` if present.
  - Examples:
    ```bash
    agentconnect config init
    agentconnect config init --force
    ```

- show
  - Purpose: Print effective (redacted) settings from SDK config loader.
  - Output: YAML if PyYAML is installed, otherwise JSON.
  - Examples:
    ```bash
    agentconnect config show
    ```

- validate
  - Purpose: Validate a YAML file against SDK models; suitable for CI.
  - Args:
    - `<file>` Path to YAML file to validate (must exist and be readable).
  - Exit codes: 0 valid, 1 invalid.
  - Examples:
    ```bash
    agentconnect config validate agentconnect.yaml
    ```

### serve

Start servers. Servers are configured via environment variables only (no YAML). For the Registry API server, variables are prefixed with `AGENTCONNECT_REGISTRY_`.

```bash
agentconnect serve --help
```

- registry
  - Purpose: Start the Registry API server (FastAPI) using env-only settings.
  - Options:
    - `--host <str>` Override server host (default comes from env).
    - `--port <int>` Override server port (default comes from env).
    - `--reload` Enable auto-reload (development).
  - Examples:
    ```bash
    agentconnect serve registry
    agentconnect serve registry --host 0.0.0.0 --port 8000
    agentconnect serve registry --reload
    ```

Developer note: You can also run the server directly: `uvicorn agentconnect.index.service:app` or `python -m agentconnect.index.service`.

### registry

Utilities for interacting with the Registry API.

```bash
agentconnect registry --help
```

- ping
  - Purpose: Health check the Registry API (`GET /health`).
  - Options:
    - `--base-url <URL>` Override base URL; defaults to `clients.registry.base_url` from `agentconnect.yaml`.
    - `--timeout <float>` Timeout in seconds (default: 3.0).
  - Exit codes:
    - 0 healthy, 3 unhealthy, 4 unreachable, 2 misconfigured.
  - Examples:
    ```bash
    agentconnect registry ping
    agentconnect registry ping --base-url http://localhost:8000
    agentconnect registry ping --timeout 5.0
    ```

### mcp

Model Context Protocol integration.

```bash
agentconnect mcp --help
```

- start agent-discovery
  - Purpose: Start the Agent Discovery MCP server (stdio).
  - Options:
    - `--registry-url <URL>` Override Registry base URL; defaults to SDK config (`clients.registry.base_url`).
  - Examples:
    ```bash
    agentconnect mcp start agent-discovery
    agentconnect mcp start agent-discovery --registry-url http://localhost:8000
    ```

### doctor

Run quick diagnostics and print a concise status summary.

```bash
agentconnect doctor
```

## Notes

- Servers are configured via environment variables only. The CLI does not read YAML for server runtime.
- CLI commands re-read configuration fresh each run via `load_settings()`. Library code often uses a process-level snapshot via `from agentconnect.config import settings`.
- Preferred quickstart commands:
  ```bash
  agentconnect config init
  agentconnect serve registry
  agentconnect registry ping
  agentconnect mcp start agent-discovery
  ```
