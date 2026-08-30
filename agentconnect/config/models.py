"""Team file models for ``agentconnect.yaml``.

Embedded ``Team("name").start()`` needs no file. This file describes a
Team the CLI can start with ``agentconnect up``: store, embeddings,
hosted Agents, and extra MCP tools. Secrets stay in the environment.

    from agentconnect.config import TeamConfig, load_team_config

    config = load_team_config()
    config.team
    config.agents[0].class_path

The example file is generated from :meth:`TeamConfig.example` so the
committed YAML cannot drift from these fields.
"""

from __future__ import annotations

import ipaddress
import re
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentconnect.config.vector import VectorSearchSettings

_IMPORT_REF = re.compile(r"^([A-Za-z_][\w.]*)\:([A-Za-z_]\w*)$")
_EMBEDDING_KEYS = {"auto", "none", "fastembed", "litellm"}


class PaymentsSettings(BaseModel):
    """Wallet defaults used by optional payment extras.

    Not part of ``agentconnect.yaml``. CDP keys stay in the environment.
    """

    default_token_symbol: str = Field(default="USDC")
    wallet_data_dir: str = Field(default="data/agent_wallets")

    @field_validator("default_token_symbol")
    @classmethod
    def normalize_token_symbol(cls, value: str) -> str:
        """Uppercase the token symbol."""
        return (value or "").upper()


class HostedAgentConfig(BaseModel):
    """One Agent class this Team process should construct and join.

    ``class`` is ``module:ClassName``. ``name`` is unique within the Team.

    .. code-block:: yaml

        - class: agents.writer:Writer
          name: writer
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    class_path: str = Field(
        alias="class",
        min_length=1,
        description="Import path module:ClassName for a BaseAgent subclass.",
    )
    name: str = Field(
        min_length=1,
        max_length=63,
        description="Agent name, unique within the Team.",
    )

    @field_validator("class_path")
    @classmethod
    def validate_class_path(cls, value: str) -> str:
        """Require ``module:Class`` form."""
        if _IMPORT_REF.fullmatch(value.strip()) is None:
            raise ValueError("class must be module:ClassName")
        return value.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Require an Agent name the Runtime will accept."""
        from agentconnect.core.address import parse_agent_name

        canonical = parse_agent_name(value)
        if canonical is None:
            raise ValueError("name is not a valid Agent name")
        return canonical


class TeamConfig(BaseModel):
    """Contents of ``agentconnect.yaml``.

    .. code-block:: yaml

        team: content-squad
        store: memory
        embeddings: auto
        host: 127.0.0.1
        port: 9000
        require_join_auth: true
        agents:
          - class: agents.writer:Writer
            name: writer
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    team: str = Field(description="Team name, a lowercase DNS label.")
    store: str = Field(
        default="memory",
        description="memory, or a Redis URL such as redis://localhost:6379/0.",
    )
    embeddings: str = Field(
        default="auto",
        description="auto | none | fastembed | fastembed:<model> | litellm | litellm:<model>.",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Loopback address agentconnect up binds.",
    )
    port: int = Field(
        default=9000,
        ge=1,
        le=65535,
        description="TCP port agentconnect up binds.",
    )
    require_join_auth: bool = Field(
        default=True,
        description="When true, every join needs a join token and identity proof.",
    )
    agents: List[HostedAgentConfig] = Field(
        default_factory=list,
        description="Agent classes this process constructs and joins.",
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Extra MCP tools as module:function import paths.",
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
                "embeddings must be auto, none, fastembed, or litellm, "
                "optionally with :model"
            )
        if key in {"auto", "none"} and sep:
            raise ValueError(f"embeddings {key} does not take a model suffix")
        if key in {"fastembed", "litellm"} and sep and not rest.strip():
            raise ValueError("embeddings model suffix must be non-empty")
        return text

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        """``up`` binds loopback only."""
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
        """Require module:function for each extra tool."""
        cleaned: List[str] = []
        for item in value:
            text = item.strip()
            if _IMPORT_REF.fullmatch(text) is None:
                raise ValueError("each tool must be module:function")
            cleaned.append(text)
        return cleaned

    @classmethod
    def example(cls) -> "TeamConfig":
        """Canonical example used to generate ``agentconnect.example.yaml``."""
        return cls(
            team="content-squad",
            store="memory",
            embeddings="auto",
            host="127.0.0.1",
            port=9000,
            require_join_auth=True,
            agents=[
                HostedAgentConfig(
                    class_path="agents.researcher:Researcher",
                    name="researcher",
                ),
                HostedAgentConfig(
                    class_path="agents.writer:Writer",
                    name="writer",
                ),
            ],
            tools=["tools.docs:search_our_docs"],
        )


__all__ = [
    "TeamConfig",
    "HostedAgentConfig",
    "PaymentsSettings",
    "VectorSearchSettings",
]
