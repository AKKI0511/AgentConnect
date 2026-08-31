"""Ready-made Agents on top of ``BaseAgent``.

These helpers are optional. The product is ``BaseAgent`` plus a Team.
``AIAgent`` needs ``pip install 'agentconnect[aiagent]'``. ``HumanAgent``
needs ``pip install 'agentconnect[cli]'``. ``TelegramAIAgent`` needs
``pip install 'agentconnect[telegram]'``.

    from agentconnect.prebuilt import AIAgent, Tool
    from agentconnect.team import Team

    agent = AIAgent(name="assistant", model="gpt-4o-mini")
    team = await Team("content-squad").start()
    await agent.join(team)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .ai_agent import AIAgent, CompletionOptions
from .loop import CompletionFn
from .tools import Tool

if TYPE_CHECKING:
    from .human_agent import HumanAgent
    from .telegram import TelegramAIAgent

__all__ = [
    "AIAgent",
    "CompletionFn",
    "CompletionOptions",
    "HumanAgent",
    "TelegramAIAgent",
    "Tool",
]


def __getattr__(name: str) -> Any:
    if name == "HumanAgent":
        try:
            from .human_agent import HumanAgent
        except ImportError as exc:
            raise ImportError(
                "HumanAgent requires the cli extra. "
                "Install with: pip install 'agentconnect[cli]'"
            ) from exc
        return HumanAgent
    if name == "TelegramAIAgent":
        try:
            from .telegram import TelegramAIAgent
        except ImportError as exc:
            raise ImportError(
                "TelegramAIAgent requires the telegram extra. "
                "Install with: pip install 'agentconnect[telegram]'"
            ) from exc
        return TelegramAIAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
