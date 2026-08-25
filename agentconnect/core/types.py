"""Shared enumerations that are not the public Message, Profile, or Address nouns.

Identity, Profile, and Message kinds live in their own modules. This module
re-exports them so existing ``core.types`` imports keep working.
"""

from __future__ import annotations

import importlib
from enum import Enum
from typing import Any


class ModelProvider(str, Enum):
    """
    Supported AI model providers.

    This enum defines the supported model providers for AI agents.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    GOOGLE = "google"


class ModelName(str, Enum):
    """
    Supported model names for each provider.

    This enum defines the specific model names available for each provider.
    """

    # OpenAI Models
    GPT4_5_PREVIEW = "gpt-4.5-preview-2025-02-27"
    GPT4_1 = "gpt-4.1"
    GPT4_1_MINI = "gpt-4.1-mini"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    O1 = "o1"
    O1_MINI = "o1-mini"
    O3 = "o3"
    O3_MINI = "o3-mini"
    O4_MINI = "o4-mini"

    # Anthropic Models
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-latest"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-latest"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-latest"
    CLAUDE_3_OPUS = "claude-3-opus-latest"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"

    # Groq Models
    LLAMA33_70B_VTL = "llama-3.3-70b-versatile"
    LLAMA3_1_8B_INSTANT = "llama-3.1-8b-instant"
    LLAMA_GUARD3_8B = "llama-guard-3-8b"
    LLAMA3_70B = "llama3-70b-8192"
    LLAMA3_8B = "llama3-8b-8192"
    MIXTRAL = "mixtral-8x7b-32768"
    GEMMA2_90B = "gemma2-9b-it"

    # Google Models
    GEMINI2_5_PRO = "gemini-2.5-pro"
    GEMINI2_5_FLASH = "gemini-2.5-flash"
    GEMINI2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI2_FLASH = "gemini-2.0-flash"
    GEMINI2_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI2_PRO_EXP = "gemini-2.0-pro-exp-02-05"
    GEMINI2_FLASH_THINKING_EXP = "gemini-2.0-flash-thinking-exp-01-21"

    @classmethod
    def get_default_for_provider(cls, provider: ModelProvider) -> "ModelName":
        """
        Get the default model for a given provider.

        Args:
            provider: The model provider to get the default model for

        Returns:
            The default model name for the provider

        Raises:
            ValueError: If no default model is defined for the provider
        """
        defaults = {
            ModelProvider.OPENAI: cls.GPT4O,
            ModelProvider.ANTHROPIC: cls.CLAUDE_3_SONNET,
            ModelProvider.GROQ: cls.LLAMA33_70B_VTL,
            ModelProvider.GOOGLE: cls.GEMINI2_FLASH,
        }

        if provider not in defaults:
            raise ValueError(f"No default model defined for provider {provider}")

        return defaults[provider]


class AgentType(str, Enum):
    """
    Types of agents in the system.

    This enum defines the different types of agents that can exist in the system.
    """

    HUMAN = "human"
    AI = "ai"


class InteractionMode(str, Enum):
    """
    Supported interaction modes between agents.

    This enum defines the different ways agents can interact with each other.
    """

    HUMAN_TO_AGENT = "human_to_agent"
    AGENT_TO_AGENT = "agent_to_agent"


class ProtocolVersion(str, Enum):
    """
    Supported protocol versions for agent communication.

    This enum defines the different protocol versions that can be used for
    communication between agents.
    """

    V1_0 = "1.0"
    V1_1 = "1.1"


class NetworkMode(str, Enum):
    """
    Network modes for agent communication.

    This enum defines the different network modes that can be used for
    agent communication.
    """

    STANDALONE = "standalone"
    NETWORKED = "networked"


_LAZY_EXPORTS = {
    "AgentIdentity": ("agentconnect.core.identity", "AgentIdentity"),
    "AgentMetadata": ("agentconnect.core.identity", "AgentMetadata"),
    "VerificationStatus": ("agentconnect.core.identity", "VerificationStatus"),
    "AgentProfile": ("agentconnect.core.profile", "AgentProfile"),
    "Capability": ("agentconnect.core.profile", "Capability"),
    "Skill": ("agentconnect.core.profile", "Skill"),
    "MessageKind": ("agentconnect.core.kinds", "MessageKind"),
}

__all__ = [
    "ModelProvider",
    "ModelName",
    "AgentType",
    "InteractionMode",
    "ProtocolVersion",
    "NetworkMode",
    *sorted(_LAZY_EXPORTS),
]


def __getattr__(name: str) -> Any:
    """Load identity, profile, and kind types without an import cycle."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    return getattr(importlib.import_module(module_name), attr)
