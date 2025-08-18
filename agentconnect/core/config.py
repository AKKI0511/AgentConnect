"""
DEPRECATED: Legacy configuration management for AgentConnect.

This module is deprecated and maintained only for backward compatibility.
Please use the new configuration system:

    from agentconnect.config import settings

instead of:

    from agentconnect.core.config import registry_settings

The new system provides configuration via `settings.registry` and related
submodels.
"""

import warnings
from typing import Dict, Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, AliasChoices

# Issue deprecation warning when this module is imported
warnings.warn(
    "agentconnect.core.config is deprecated. Use 'from agentconnect.config import settings' instead.",
    DeprecationWarning,
    stacklevel=2,
)


class VectorSearchSettings(BaseSettings):
    """DEPRECATED: Use agentconnect.config.settings.registry.vector_search instead."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_REGISTRY_", extra="allow"
    )

    model_name: str = "sentence-transformers/all-mpnet-base-v2"
    cache_folder: str = "./.cache/huggingface/embeddings"
    vector_store_path: str = "./.cache/vector_stores"
    in_memory: bool = True

    def as_dict(self) -> Dict[str, Any]:
        """Convert settings to a dictionary."""
        return self.model_dump()


class RegistryAPISettings(BaseSettings):
    """DEPRECATED: Use RegistryServerSettings from agentconnect.config.models for servers, or settings.clients.registry for clients."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_REGISTRY_API_", extra="allow"
    )

    host: str = Field(default="localhost", validation_alias=AliasChoices("API_HOST"))
    port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG"))
    allowed_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        validation_alias=AliasChoices("ALLOWED_ORIGINS"),
    )

    @field_validator("allowed_origins", mode="before")
    def parse_allowed_origins(cls, v):
        """Parse allowed origins from string if it's not already a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


class LoggingSettings(BaseSettings):
    """DEPRECATED: Global logging moved out of settings. Use `agentconnect.utils.logging_config`."""

    model_config = SettingsConfigDict(env_prefix="AGENTCONNECT_", extra="allow")

    level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        validation_alias=AliasChoices("LOG_FORMAT"),
    )

    @field_validator("level")
    def validate_log_level(cls, v):
        """Validate log level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            return "INFO"  # Default to INFO if invalid
        return v.upper()


class RegistrySettings(BaseSettings):
    """DEPRECATED: Use agentconnect.config.settings.registry instead."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_REGISTRY_", env_file=".env", extra="allow"
    )

    vector_search: VectorSearchSettings = VectorSearchSettings()
    api: RegistryAPISettings = RegistryAPISettings()
    logging: LoggingSettings = LoggingSettings()

    def get_vector_search_config(self) -> Dict[str, Any]:
        """Get vector search configuration as a dictionary."""
        return self.vector_search.as_dict()


# Create a single instance to be imported by other modules
# This provides backward compatibility while the codebase migrates
registry_settings = RegistrySettings()
