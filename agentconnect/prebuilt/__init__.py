"""
Ready-made agents for the AgentConnect framework.

These helpers sit on top of ``BaseAgent``. They are optional conveniences.

Key components:

- **AIAgent**: Independent AI-powered agent with potential for internal multi-agent structures
- **HumanAgent**: Human-in-the-loop agent that can interact securely with the decentralized network
- **TelegramAIAgent**: AI agent that integrates with Telegram for user interactions
- **MemoryType**: Enum for different types of agent memory
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .ai_agent import AIAgent, MemoryType

if TYPE_CHECKING:
    from .human_agent import HumanAgent
    from .telegram import TelegramAIAgent

__all__ = ["AIAgent", "HumanAgent", "TelegramAIAgent", "MemoryType"]


def __getattr__(name: str) -> Any:
    if name == "HumanAgent":
        try:
            from .human_agent import HumanAgent
        except ImportError as exc:
            raise ImportError(
                "HumanAgent requires the cli extra. Install with: pip install 'agentconnect[cli]'"
            ) from exc
        return HumanAgent
    if name == "TelegramAIAgent":
        try:
            from .telegram import TelegramAIAgent
        except ImportError as exc:
            raise ImportError(
                "TelegramAIAgent requires the telegram extra. Install with: pip install 'agentconnect[telegram]'"
            ) from exc
        return TelegramAIAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
