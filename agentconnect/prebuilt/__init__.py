"""Optional Agents for when you do not already have a harness loop.

Subclass `BaseAgent` when a harness already answers Team requests.
Use `AIAgent` for a LiteLLM model id. Use `HumanAgent` when a person
types the reply. Use `TelegramAIAgent` when Telegram chats should use
that same model.

`AIAgent` needs `agentconnect[aiagent]`. `HumanAgent` needs
`agentconnect[cli]`. `TelegramAIAgent` needs `agentconnect[telegram]`.
Provider keys and `TELEGRAM_BOT_TOKEN` stay in the environment.

Examples:
    `team` is started and `researcher` has joined. After
    `pip install 'agentconnect[aiagent]'`:

    ```python
    from agentconnect.prebuilt import AIAgent

    writer = AIAgent(
        name="writer",
        model="gpt-4o-mini",
        instructions="Draft short release notes from the request.",
    )
    await writer.join(team)
    ticket = await researcher.ask(
        "writer",
        "Draft a release note: search is faster, and deadlines now "
        "appear in the activity log.",
    )
    if ticket.state == "completed":
        print(ticket.response.content)
    ```
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ai_agent import AIAgent, CompletionOptions
from .loop import CompletionFn

if TYPE_CHECKING:
    from .human_agent import HumanAgent
    from .telegram import TelegramAIAgent

__all__ = [
    "AIAgent",
    "CompletionFn",
    "CompletionOptions",
    "HumanAgent",
    "TelegramAIAgent",
]


def __getattr__(name: str) -> object:
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
