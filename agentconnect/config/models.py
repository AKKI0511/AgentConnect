"""
Pydantic configuration models for AgentConnect.

This module defines the comprehensive configuration structure using Pydantic models.
Only essential, developer-facing settings are exposed - internal tuning parameters
remain in the code as defaults.

Global configuration precedence (highest to lowest):
1) Runtime keyword overrides
2) agentconnect.yaml
3) Model defaults

Environment variables are not read by the global settings system. They are reserved
for secrets and are consumed directly by the specific subsystems that require them
(e.g., provider SDKs, external clients).
"""

import os
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator, SecretStr


# === REGISTRY RUNTIME CONFIGURATIONS ===
class InMemoryConfig(BaseModel):
    """In-memory Qdrant configuration (for development)."""

    type: Literal["in_memory"] = "in_memory"


class LocalFileConfig(BaseModel):
    """Local file-based Qdrant configuration."""

    type: Literal["local_file"] = "local_file"
    path: str = Field(
        default="./local_qdrant_db",
        description="Directory path for local Qdrant storage",
    )


class RemoteConfig(BaseModel):
    """Remote Qdrant server configuration."""

    type: Literal["remote"] = "remote"
    url: str = Field(
        description="Qdrant server URL (e.g., 'http://localhost:6333' or 'https://xyz.qdrant.io')"
    )
    api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("QDRANT_API_KEY")),
        description="API key for Qdrant authentication (read from QDRANT_API_KEY environment variable)",
    )

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        """Validate URL format."""
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


# === VECTOR SEARCH SETTINGS ===
class VectorSearchAdvancedSettings(BaseModel):
    """Advanced configuration for vector search (for power users)."""

    # === CONNECTION ADVANCED OPTIONS ===
    timeout: int = Field(
        default=30, ge=1, description="Qdrant client timeout in seconds"
    )
    grpc_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Qdrant gRPC port (for remote deployments only)",
    )
    prefer_grpc: bool = Field(
        default=False, description="Use gRPC instead of HTTP for Qdrant communication"
    )

    # === PERFORMANCE TUNING ===
    use_quantization: bool = Field(
        default=True,
        description="Enable INT8 vector quantization (4x storage reduction, <1% accuracy loss)",
    )
    vectors_on_disk: bool = Field(
        default=False,
        description="Store vectors on disk instead of memory (slower but less RAM)",
    )
    index_on_disk: bool = Field(
        default=False, description="Store search index on disk instead of memory"
    )
    batch_size: int = Field(
        default=100, ge=1, description="Batch size for indexing operations"
    )


class VectorSearchSettings(BaseModel):
    """Vector search configuration for agent registry."""

    # === ESSENTIAL SETTINGS ===
    model_name: str = Field(
        default="sentence-transformers/all-mpnet-base-v2",
        description="Embedding model for semantic search",
    )
    cache_folder: str = Field(
        default="./.cache/huggingface/embeddings",
        description="Local cache directory for embeddings",
    )
    vector_store_path: str = Field(
        default="./.cache/vector_stores",
        description="Local vector store storage path (used for temporary files)",
    )

    # === DEPLOYMENT MODE (choose exactly one) ===
    deployment: Union[InMemoryConfig, LocalFileConfig, RemoteConfig] = Field(
        default_factory=InMemoryConfig,
        discriminator="type",
        description="Deployment configuration - choose exactly one mode",
    )

    # === ADVANCED SETTINGS (for power users) ===
    advanced: VectorSearchAdvancedSettings = Field(
        default_factory=VectorSearchAdvancedSettings,
        description="Advanced settings for performance tuning and fine-grained control",
    )

    def get_connection_config(self) -> Dict[str, Any]:
        """Get connection configuration for the vector implementation."""
        base_config = {
            "timeout": self.advanced.timeout,
            "prefer_grpc": self.advanced.prefer_grpc,
        }

        if self.advanced.grpc_port:
            base_config["grpc_port"] = self.advanced.grpc_port

        if self.deployment.type == "in_memory":
            return {**base_config, "in_memory": True}
        elif self.deployment.type == "local_file":
            return {**base_config, "path": self.deployment.path}
        elif self.deployment.type == "remote":
            config = {**base_config, "url": self.deployment.url}
            return config

        return base_config

    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance-related configuration."""
        return {
            "use_quantization": self.advanced.use_quantization,
            "vectors_on_disk": self.advanced.vectors_on_disk,
            "index_on_disk": self.advanced.index_on_disk,
            "batch_size": self.advanced.batch_size,
        }


# === REGISTRY SETTINGS ===
class RegistrySettings(BaseModel):
    """Registry subsystem configuration.

    The registry only needs vector-search / storage related configuration.

    Runtime parameters for the standalone Registry API server are configured
    separately in `agentconnect.config.servers` via environment variables
    with the `AGENTCONNECT_REGISTRY_` prefix. See `agentconnect.config.servers.RegistryAPISettings`.
    """

    vector_search: VectorSearchSettings = Field(default_factory=VectorSearchSettings)

    def get_vector_search_config(self) -> Dict[str, Any]:
        """Get vector search configuration as dictionary for backward compatibility."""
        return self.vector_search.model_dump()


# === COMMUNICATION SETTINGS ===
class CommunicationSettings(BaseModel):
    """Communication hub configuration for A2A messaging."""

    enable_message_history: bool = Field(
        default=True,
        description="Enable message history tracking (disable for better performance)",
    )


# === CLIENT SETTINGS ===
class RegistryClientSettings(BaseModel):
    """Configuration for the Registry API Client."""

    base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for the Registry API. Configure via agentconnect.yaml under clients.registry.base_url.",
    )
    default_timeout: float = Field(
        default=30.0, description="Default timeout for HTTP requests in seconds."
    )
    connect_timeout: float = Field(
        default=10.0, description="Timeout for establishing connections in seconds."
    )
    read_timeout: float = Field(
        default=30.0, description="Timeout for reading responses in seconds."
    )
    pool_timeout: float = Field(
        default=5.0,
        description="Timeout for acquiring a connection from the pool in seconds.",
    )
    max_retries: int = Field(
        default=3, ge=0, description="Maximum number of retries for failed requests."
    )
    retry_backoff_factor: float = Field(
        default=0.5,
        ge=0,
        description="Backoff factor for retry attempts (wait_time = factor * (2**attempt)).",
    )
    retryable_status_codes: List[int] = Field(
        default_factory=lambda: [502, 503, 504],
        description="HTTP status codes that trigger a retry.",
    )
    max_connections: int = Field(
        default=10, ge=1, description="Maximum number of connections in the pool."
    )
    max_keepalive_connections: int = Field(
        default=5, ge=1, description="Maximum number of keep-alive connections."
    )


class ClientSettings(BaseModel):
    """Configurations for API clients."""

    registry: RegistryClientSettings = Field(default_factory=RegistryClientSettings)
    # Future clients can be added here


# === MCP SETTINGS ===
class MCPAgentDiscoverySettings(BaseModel):
    """Configuration for the Agent Discovery MCP tool."""

    enabled: bool = Field(default=True, description="Enable the agent discovery tool")
    top_k: int = Field(
        default=5,
        ge=1,
        description="Default number of agent results to return when not specified",
    )
    strictness: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Default similarity threshold (0.0-1.0)",
    )
    output_detail: Literal["minimal", "summary", "capabilities", "full"] = Field(
        default="summary", description="Default level of detail for search results"
    )


class MCPSettings(BaseModel):
    """Configuration for MCP (Model Context Protocol) servers."""

    agent_discovery: MCPAgentDiscoverySettings = Field(
        default_factory=MCPAgentDiscoverySettings,
        description="Agent discovery MCP configuration",
    )


# === PAYMENTS SETTINGS ===
class PaymentsSettings(BaseModel):
    """Payments configuration."""

    default_token_symbol: str = Field(
        default="USDC",
        description="Default token symbol to use for payments (e.g., 'USDC' or 'ETH').",
    )
    wallet_data_dir: str = Field(
        default="data/agent_wallets",
        description="Directory for persisting agent wallet data.",
    )

    @field_validator("default_token_symbol")
    @classmethod
    def normalize_token_symbol(cls, v: str) -> str:
        """Normalize token symbols to uppercase for consistent comparisons"""
        return (v or "").upper()


# === LOGGING SETTINGS ===
class LoggingSettings(BaseModel):
    """Logging configuration settings.

    Not part of global settings; retained for potential reuse.
    """

    level: str = Field(
        default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )
    json_output: bool = Field(default=False, description="Output logs in JSON format")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is supported."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            return "INFO"  # Default to INFO if invalid
        return v_upper


# === AGENTCONNECT SETTINGS ===
class AgentConnectSettings(BaseModel):
    """
    Main configuration class for AgentConnect.

    Precedence (highest to lowest):
    1. Runtime kwargs
    2. agentconnect.yaml file
    3. Hard-coded defaults
    """

    # Core subsystems
    registry: RegistrySettings = Field(default_factory=RegistrySettings)
    communication: CommunicationSettings = Field(default_factory=CommunicationSettings)
    clients: ClientSettings = Field(default_factory=ClientSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    payments: PaymentsSettings = Field(default_factory=PaymentsSettings)

    # Global settings
    project_name: str = Field(default="AgentConnect", description="Project name")

    @classmethod
    def create_from_dict(cls, config_dict: Dict[str, Any]) -> "AgentConnectSettings":
        """Create settings instance from configuration dictionary."""
        return cls(**config_dict)

    def get_registry_config(self) -> Dict[str, Any]:
        """Get registry configuration for backward compatibility."""
        return {
            "vector_search_config": self.registry.get_vector_search_config(),
        }

    def model_dump_yaml_safe(self) -> Dict[str, Any]:
        """Export configuration in YAML-safe format (no secrets)."""
        data = self.model_dump()

        def redact_secrets(obj: Any) -> Any:
            """Replace secrets and coerce remaining values to YAML-safe types."""
            if isinstance(obj, SecretStr):
                return "***REDACTED***"
            if isinstance(obj, dict):
                return {k: redact_secrets(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [redact_secrets(v) for v in obj]
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            return str(obj)

        return redact_secrets(data)
