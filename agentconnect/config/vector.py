"""Qdrant vector-search settings for the optional Index service.

These models are not part of ``agentconnect.yaml``. The Index process
reads them from ``AGENTCONNECT_REGISTRY_*`` environment variables.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, SecretStr, field_validator
from typing import Literal


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
    url: str = Field(description="Qdrant server URL (e.g., 'http://localhost:6333')")
    api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("QDRANT_API_KEY") or ""),
        description="API key from QDRANT_API_KEY",
    )

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        """Require an http or https URL."""
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class VectorSearchAdvancedSettings(BaseModel):
    """Advanced Qdrant connection and storage flags."""

    timeout: int = Field(default=30, ge=1, description="Client timeout in seconds")
    grpc_port: Optional[int] = Field(default=None, ge=1, le=65535)
    prefer_grpc: bool = Field(default=False)
    use_quantization: bool = Field(default=True)
    vectors_on_disk: bool = Field(default=False)
    index_on_disk: bool = Field(default=False)
    batch_size: int = Field(default=100, ge=1)


class VectorSearchSettings(BaseModel):
    """Vector search configuration for the Index service."""

    model_name: str = Field(
        default="hashed",
        description="Embedding model for Index search. hashed, or a fastembed model id.",
    )
    cache_folder: str = Field(
        default="./.cache/huggingface/embeddings",
        description="Local cache directory for embeddings",
    )
    vector_store_path: str = Field(
        default="./.cache/vector_stores",
        description="Local vector store storage path",
    )
    deployment: Union[InMemoryConfig, LocalFileConfig, RemoteConfig] = Field(
        default_factory=InMemoryConfig,
        discriminator="type",
    )
    advanced: VectorSearchAdvancedSettings = Field(
        default_factory=VectorSearchAdvancedSettings
    )

    def get_connection_config(self) -> Dict[str, Any]:
        """Return Qdrant client kwargs for this deployment."""
        base_config: Dict[str, Any] = {
            "timeout": self.advanced.timeout,
            "prefer_grpc": self.advanced.prefer_grpc,
        }
        if self.advanced.grpc_port:
            base_config["grpc_port"] = self.advanced.grpc_port
        if self.deployment.type == "in_memory":
            return {**base_config, "in_memory": True}
        if self.deployment.type == "local_file":
            return {**base_config, "path": self.deployment.path}
        if self.deployment.type == "remote":
            return {**base_config, "url": self.deployment.url}
        return base_config

    def get_performance_config(self) -> Dict[str, Any]:
        """Return quantization and disk flags."""
        return {
            "use_quantization": self.advanced.use_quantization,
            "vectors_on_disk": self.advanced.vectors_on_disk,
            "index_on_disk": self.advanced.index_on_disk,
            "batch_size": self.advanced.batch_size,
        }

    def get_vector_search_config(self) -> Dict[str, Any]:
        """Return this model as a plain dict."""
        return self.model_dump()
