"""Records and settings for the optional Index."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentconnect.core.address import parse_agent_name
from agentconnect.core.base import JsonObject
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.profile import Skill

_COLLECTIONS = frozenset({"skills", "tags", "custom_metadata"})


def _canonical_agent_id(value: str) -> str:
    """Return a lowercase Index id, or raise when it is not URL-safe."""
    if not isinstance(value, str):
        raise ValueError("agent_id must be 1-63 ASCII letters, digits, '_' or '-'")
    canonical = parse_agent_name(value)
    if canonical is None:
        raise ValueError("agent_id must be 1-63 ASCII letters, digits, '_' or '-'")
    return canonical


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
        description="Defaults to http://127.0.0.1:3000.",
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


class AgentRegistration(BaseModel):
    """One agent record you submit to an Index.

    `agent_id` is stored lowercase and must be safe to place in a URL path.
    `identity` is an [`AgentIdentity`][agentconnect.core.identity.AgentIdentity].
    The DID must match the public key. Stored copies and JSON omit the
    private key. `skills` use [`Skill`][agentconnect.core.profile.Skill].
    The record disappears when the process stops.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    identity: AgentIdentity
    name: str | None = None
    summary: str | None = None
    description: str | None = None
    skills: list[Skill] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    url: str | None = None
    custom_metadata: JsonObject = Field(default_factory=dict)

    @field_validator("agent_id")
    @classmethod
    def _agent_id(cls, value: str) -> str:
        return _canonical_agent_id(value)

    @field_validator("identity", mode="before")
    @classmethod
    def _load_identity(cls, value: object) -> object:
        if isinstance(value, AgentIdentity):
            return value
        if isinstance(value, dict):
            try:
                return AgentIdentity.from_dict(value)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("identity is missing did or public_key") from exc
        raise ValueError("identity is missing did or public_key")

    @field_serializer("identity")
    def _public_identity(self, identity: AgentIdentity) -> JsonObject:
        return identity.to_dict()

    @model_validator(mode="after")
    def _did_matches_key(self) -> AgentRegistration:
        if not self.identity.matches_did():
            raise ValueError("DID does not match the public key")
        return self


class RegistrationUpdate(BaseModel):
    """Fields to change on a stored registration.

    Omitted fields stay as they are. Null clears `name`, `summary`,
    `description`, or `url`. `skills`, `tags`, and `custom_metadata`
    clear with an empty value and reject null.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    summary: str | None = None
    description: str | None = None
    skills: list[Skill] | None = None
    tags: list[str] | None = None
    url: str | None = None
    custom_metadata: JsonObject | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_null_collections(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key, value in data.items():
                if key in _COLLECTIONS and value is None:
                    raise ValueError(f"{key} cannot be null")
        return data


class IndexQuery(BaseModel):
    """Text search over the records one Index process is holding."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    tags: list[str] = Field(default_factory=list)


class IndexSearchHit(BaseModel):
    """One stored registration and the embedder's similarity score."""

    registration: AgentRegistration
    score: float
