"""Optional ready-made Agents on top of `BaseAgent`.

The product is `BaseAgent` plus a Team. This package is convenience:
a LiteLLM loop, a stdin human, and a Telegram bot. None of these is
required to join a Team.

`AIAgent` needs `pip install 'agentconnect[aiagent]'`. `HumanAgent`
needs `pip install 'agentconnect[cli]'`. `TelegramAIAgent` needs
`pip install 'agentconnect[telegram]'`. `Tool` is the same callable
wrapper as `agentconnect.agent.tools.Tool`.

Pass extra tools as annotated functions or explicit `Tool` objects.
Team coordination tools (`find`, `ask`, `tell`, `get_result`,
`get_history`, `get_profiles`) attach from the Session. `model` is a
LiteLLM model id. Provider keys stay in the environment.

Examples:
    For a started Team, after `pip install 'agentconnect[aiagent]'`.
    Close the Session with `leave` when finished:

    ```python
    from agentconnect.prebuilt import AIAgent

    agent = AIAgent(name="assistant", model="gpt-4o-mini")
    await agent.join(team)
    await agent.leave()
    ```
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
