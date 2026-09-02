"""LiteLLM model and provider labels used by the demo API.

These enumerations used to live in ``core.types``. Model choice on a Team
Agent is a string. The demo keeps named values so its config and Pydantic
models keep working.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ModelProvider", "ModelName"]


class ModelProvider(str, Enum):
    """Demo provider labels. Team Agents pass a LiteLLM model string."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    GOOGLE = "google"


class ModelName(str, Enum):
    """Demo model ids. Team Agents pass these as plain strings."""

    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    LLAMA3_70B = "llama3-70b-8192"
    GEMINI2_FLASH = "gemini-2.0-flash"
    GEMINI2_FLASH_LITE = "gemini-2.0-flash-lite"

    @classmethod
    def get_default_for_provider(cls, provider: ModelProvider | str) -> "ModelName":
        """Return a default model id for a demo provider label."""
        key = provider.value if isinstance(provider, ModelProvider) else str(provider)
        return {
            ModelProvider.OPENAI.value: cls.GPT4O_MINI,
            ModelProvider.ANTHROPIC.value: cls.CLAUDE_3_OPUS,
            ModelProvider.GROQ.value: cls.LLAMA3_70B,
            ModelProvider.GOOGLE.value: cls.GEMINI2_FLASH,
        }.get(key, cls.GPT4O_MINI)
