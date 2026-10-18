"""Team file models for `agentconnect.toml` and `[tool.agentconnect]`.

[`Team`][agentconnect.team.runtime.Team] started in Python needs no file.
Secrets stay in the environment.
"""

from __future__ import annotations

import ipaddress
import re
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentconnect.core.base import JsonObject

_IMPORT_REF = re.compile(r"^([A-Za-z_][\w.]*)\:([A-Za-z_]\w*)$")
_EMBEDDING_KEYS = {"auto", "none", "hashed", "fastembed", "openai", "litellm"}


class HostedAgentConfig(BaseModel):
    """One Agent this Team process constructs and joins.

    `entrypoint` is `module:Name`: a [`BaseAgent`][agentconnect.agent.base.BaseAgent]
    subclass or a synchronous factory. Both receive `name=<mapping key>` plus
    optional `kwargs`. `kwargs` is owned by that class or factory; do not put
    `name` there.

    ```toml
    [agents.writer]
    entrypoint = "agents.writer:Writer"
    kwargs.model = "provider/model"
    ```
    """

    model_config = ConfigDict(extra="forbid")

    entrypoint: str = Field(
        min_length=1,
        description=(
            "Import path `module:Name` of a BaseAgent subclass or a "
            "synchronous factory create(name, **kwargs) that returns an "
            "unjoined BaseAgent."
        ),
    )
    kwargs: JsonObject = Field(
        default_factory=dict,
        description="Arguments passed to your class or factory.",
    )

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint(cls, value: str) -> str:
        """Require `module:Name` form."""
        if _IMPORT_REF.fullmatch(value.strip()) is None:
            raise ValueError("entrypoint must be module:Name")
        return value.strip()

    @model_validator(mode="after")
    def reject_kwargs_name(self) -> "HostedAgentConfig":
        """The mapping key is the Agent name."""
        if "name" in self.kwargs:
            raise ValueError(
                "kwargs must not include name; the mapping key is the Agent name"
            )
        return self


class TeamConfig(BaseModel):
    """Contents of a Team file.

    A standalone `agentconnect.toml` uses this tree. `pyproject.toml` prefixes
    the same tree with `[tool.agentconnect]`.

    ```toml
    team = "content-squad"

    [agents.researcher]
    entrypoint = "agents.researcher:Researcher"

    [agents.writer]
    entrypoint = "agents.writer:Writer"
    kwargs.model = "provider/model"
    ```
    """

    model_config = ConfigDict(extra="forbid")

    team: str = Field(description="Team name, a lowercase DNS label.")
    store: str = Field(
        default="memory",
        description="memory, or a Redis URL such as `redis://localhost:6379/0`.",
    )
    embeddings: str = Field(
        default="auto",
        description=(
            "auto, none, hashed, fastembed, openai, or litellm. "
            "The last three accept an optional :model suffix. "
            "auto uses a local ONNX model when the embeddings extra is "
            "installed, otherwise hashed n-grams, and does not send "
            "Profiles or queries to a hosted embedder."
        ),
    )
    host: str = Field(
        default="127.0.0.1",
        description="Loopback address `agentconnect up` binds.",
    )
    port: int = Field(
        default=9000,
        ge=1,
        le=65535,
        description="TCP port `agentconnect up` binds.",
    )
    require_join_auth: bool = Field(
        default=True,
        description="When true, every join needs a join token and identity proof.",
    )
    agents: dict[str, HostedAgentConfig] = Field(
        default_factory=dict,
        description=(
            "Agents this process constructs and joins, keyed by canonical "
            "Agent name. Independently deployed Agents join by URL and are "
            "not listed."
        ),
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Extra MCP tools as `module:function` import paths.",
    )

    @field_validator("team")
    @classmethod
    def validate_team(cls, value: str) -> str:
        """Require a Team name the Runtime will accept."""
        from agentconnect.core.address import parse_team_name

        canonical = parse_team_name(value)
        if canonical is None:
            raise ValueError("team is not a valid Team name")
        return canonical

    @field_validator("store")
    @classmethod
    def validate_store(cls, value: str) -> str:
        """Allow memory or a Redis URL."""
        text = value.strip()
        if text == "memory":
            return text
        if text.startswith("redis://") or text.startswith("rediss://"):
            return text
        raise ValueError("store must be memory or a redis:// URL")

    @field_validator("embeddings")
    @classmethod
    def validate_embeddings(cls, value: str) -> str:
        """Allow the same string forms Team(embeddings=...) accepts."""
        text = value.strip()
        key, sep, rest = text.partition(":")
        if key not in _EMBEDDING_KEYS:
            raise ValueError(
                "embeddings must be auto, none, hashed, fastembed, openai, or "
                "litellm, optionally with :model"
            )
        if key in {"auto", "none", "hashed"} and sep:
            raise ValueError(f"embeddings {key} does not take a model suffix")
        if key in {"fastembed", "openai", "litellm"} and sep and not rest.strip():
            raise ValueError("embeddings model suffix must be non-empty")
        return text

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        """`up` binds loopback only."""
        host = value.strip()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return host
        try:
            if ipaddress.ip_address(host).is_loopback:
                return host
        except ValueError:
            pass
        raise ValueError("host must be a loopback address")

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, value: List[str]) -> List[str]:
        """Require `module:function` for each extra tool."""
        cleaned: List[str] = []
        for item in value:
            text = item.strip()
            if _IMPORT_REF.fullmatch(text) is None:
                raise ValueError("each tool must be `module:function`")
            cleaned.append(text)
        return cleaned

    @field_validator("agents", mode="before")
    @classmethod
    def canonical_agent_names(cls, value: object) -> object:
        """Require a name mapping and reject invalid or colliding names."""
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("agents must be a table of Agent names, not an array")
        from agentconnect.core.address import parse_agent_name

        remapped: dict[str, object] = {}
        original_for: dict[str, str] = {}
        for key, spec in value.items():
            if not isinstance(key, str):
                raise ValueError("Agent names must be strings")
            canonical = parse_agent_name(key)
            if canonical is None:
                raise ValueError(f"{key!r} is not a valid Agent name")
            if canonical in remapped:
                raise ValueError(
                    f"Agent names {original_for[canonical]!r} and {key!r} collide"
                )
            remapped[canonical] = spec
            original_for[canonical] = key
        return remapped

    @classmethod
    def example(cls) -> "TeamConfig":
        """Canonical example for a standalone Team file."""
        return cls(
            team="content-squad",
            store="memory",
            embeddings="auto",
            host="127.0.0.1",
            port=9000,
            require_join_auth=True,
            agents={
                "researcher": HostedAgentConfig(
                    entrypoint="agents.researcher:Researcher",
                ),
                "writer": HostedAgentConfig(
                    entrypoint="agents.writer:Writer",
                    kwargs={"model": "provider/model"},
                ),
            },
            tools=["tools.docs:search_our_docs"],
        )


__all__ = [
    "TeamConfig",
    "HostedAgentConfig",
]
