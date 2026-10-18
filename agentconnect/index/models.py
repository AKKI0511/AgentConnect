"""Settings and search hits for the optional Index."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentconnect.core.directory import DirectoryEntry

__all__ = ["IndexSearchHit", "IndexSettings"]


class IndexSettings(BaseSettings):
    """Process settings from `AGENTCONNECT_INDEX_*`.

    `python -m agentconnect.index.service` listens on loopback only.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENTCONNECT_INDEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(
        default="127.0.0.1",
        description="Loopback address used by the built-in server.",
    )
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = Field(default="INFO")
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:3000"],
        description="CORS origins the built-in server allows.",
    )
    model_name: str = Field(
        default="hashed",
        description="hashed, or a fastembed model id. A failed load stops startup.",
    )

    @field_validator("log_level")
    @classmethod
    def _log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        text = value.upper()
        return text if text in allowed else "INFO"

    @field_validator("model_name")
    @classmethod
    def _model_name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("model_name is required")
        return text


class IndexSearchHit(BaseModel):
    """One stored snapshot and the embedder's similarity score.

    `entry` is a [`DirectoryEntry`][agentconnect.core.directory.DirectoryEntry].
    """

    model_config = ConfigDict(extra="forbid")

    entry: DirectoryEntry
    score: float
