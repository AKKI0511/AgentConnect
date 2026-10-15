"""
Configuration for the standalone servers.
"""

import json
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources.providers.env import (
    EnvSettingsSource as PydanticEnvSettingsSource,
)

from agentconnect.config.vector import VectorSearchSettings


# === STANDALONE SERVER SETTINGS ===
class RegistryAPISettings(BaseSettings):
    """Registry API Server configuration loaded from environment variables only.

    For System Operators deploying infrastructure. Environment variables must be prefixed
    with AGENTCONNECT_REGISTRY_ to avoid collisions.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_REGISTRY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",  # Use double-underscore for nested fields
    )

    host: str = Field(
        default="localhost",
        description="Server host address. Use '0.0.0.0' to be accessible from outside a container.",
    )
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    reload: bool = Field(
        default=False,
        description="Enable Uvicorn's auto-reload on code changes (for development).",
    )
    log_level: str = Field(
        default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins",
    )

    # Vector store configuration for the registry
    vector_search: VectorSearchSettings = Field(
        default_factory=VectorSearchSettings,
        description="Vector search configuration for the underlying vector store",
    )

    # Optional JSON override for the entire vector_search block (highest precedence)
    # Env var: AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON
    vector_search_json: Optional[str] = Field(
        default=None,
        description=(
            "JSON override for vector_search settings. When set, it overrides all nested "
            "vector_search env keys."
        ),
    )

    @staticmethod
    def settings_customise_sources(
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use a lenient env source to avoid hard JSON parsing for complex fields.

        This ensures values like "a,b" for list fields don't raise during env parsing
        and can be handled by our field validators instead.
        """

        class LenientEnvSettingsSource(PydanticEnvSettingsSource):
            """Lenient environment settings source to bypass JSON decoding for allowed_origins."""

            def decode_complex_value(
                self, field_name: str, field: FieldInfo, value: object
            ) -> object:
                """Lenient environment settings source to bypass JSON decoding for allowed_origins."""
                try:
                    return super().decode_complex_value(field_name, field, value)
                except Exception:
                    # Only bypass JSON decoding for the specific field that accepts CSV
                    if field_name == "allowed_origins":
                        return value
                    # Preserve default behavior (raise) for other fields
                    raise

        return (
            LenientEnvSettingsSource(settings_cls),
            init_settings,
            dotenv_settings,
            file_secret_settings,
        )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is supported."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            return "INFO"  # Default to INFO if invalid
        return v_upper

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> object:
        """Support JSON or comma-separated strings for allowed_origins."""
        if v is None:
            return v
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            raw = v.strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def apply_vector_search_json_override(self) -> "RegistryAPISettings":
        """Apply JSON override for vector_search after initial env loading.

        Precedence: JSON env > nested env keys > defaults.
        """
        if self.vector_search_json:
            try:
                data = json.loads(self.vector_search_json)
                self.vector_search = VectorSearchSettings.model_validate(data)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON for AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON: {e}"
                ) from e
        return self


class InboxServerSettings(BaseSettings):
    """Inbox Server configuration loaded from environment variables only.

    Environment variables must be prefixed with AGENTCONNECT_INBOX_.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_INBOX_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    host: str = Field(default="0.0.0.0", description="Inbox server host")
    port: int = Field(default=8081, ge=1, le=65535, description="Inbox server port")
    path: str = Field(
        default="/agentconnect/collaboration",
        description="Base path for collaboration endpoints",
    )
    # Auth (env-only; no YAML). Header name and the ENV VAR KEY that contains the token
    auth_header_name: str = Field(
        default="Authorization",
        description="HTTP header name for inbound auth (e.g., 'Authorization')",
    )
    bearer_token_env_var: str = Field(
        default="AGENTCONNECT_INBOX_BEARER_TOKEN",
        description=(
            "Environment variable name that stores the expected bearer token for inbox auth"
        ),
    )
    idempotency_header_name: str = Field(
        default="X-Idempotency-Key",
        description="Header name for idempotency key enforcement on POST",
    )
    require_auth: bool = Field(
        default=False,
        description=(
            "If True, reject requests without a valid Bearer token in the configured header"
        ),
    )
    allowed_senders: List[str] = Field(
        default_factory=list,
        description="Optional whitelist of allowed sender IDs",
    )

    # Limits
    max_body_bytes: int = Field(
        default=128 * 1024, ge=1024, description="Maximum request body size"
    )
    max_content_length: int = Field(
        default=4096, ge=1, description="Maximum message content length (chars)"
    )
    max_metadata_bytes: int = Field(
        default=8192, ge=0, description="Maximum metadata size in bytes"
    )
    clock_skew_seconds: int = Field(
        default=300, ge=0, description="Allowed clock skew for message timestamps"
    )
    require_idempotency_header: bool = Field(
        default=True, description="Require X-Idempotency-Key header on POST"
    )
    replay_ttl_seconds: int = Field(
        default=600,
        ge=1,
        description="TTL window for replay protection keyed by message.id",
    )

    # Rate limits (token buckets)
    global_rate_per_sec: float = Field(
        default=50.0, ge=0.0, description="Global tokens added per second"
    )
    global_burst: int = Field(default=100, ge=1, description="Global burst size")
    per_sender_rate_per_sec: float = Field(
        default=5.0, ge=0.0, description="Per-sender tokens added per second"
    )
    per_sender_burst: int = Field(default=10, ge=1, description="Per-sender burst size")
