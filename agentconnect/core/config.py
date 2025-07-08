"""
Configuration management for AgentConnect.

This module provides a Pydantic-based configuration system that loads settings
from environment variables, .env files, and provides sensible defaults.
"""

from typing import Dict, Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class VectorSearchSettings(BaseSettings):
    """Settings for vector search capabilities in the registry."""

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
    """Settings for the Registry API Server."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_REGISTRY_API_", extra="allow"
    )

    host: str = Field(default="localhost", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    allowed_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        env="ALLOWED_ORIGINS",
    )

    @field_validator("allowed_origins", mode="before")
    def parse_allowed_origins(cls, v):
        """Parse allowed origins from string if it's not already a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


class LoggingSettings(BaseSettings):
    """Settings for logging configuration."""

    model_config = SettingsConfigDict(env_prefix="AGENTCONNECT_", extra="allow")

    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT"
    )

    @field_validator("level")
    def validate_log_level(cls, v):
        """Validate log level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            return "INFO"  # Default to INFO if invalid
        return v.upper()


class RegistrySettings(BaseSettings):
    """Registry-specific settings."""

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
registry_settings = RegistrySettings()
