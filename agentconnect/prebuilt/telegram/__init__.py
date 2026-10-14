"""Telegram Agent for AgentConnect.

`TelegramAIAgent` extends `AIAgent` with a Telegram bot. Join a Team,
then `run()` to poll.

Examples:
    For a started Team. Close the Session with `leave` when finished:

    ```python
    from agentconnect.prebuilt import TelegramAIAgent

    agent = TelegramAIAgent(
        name="telegram-bot",
        model="gpt-4o-mini",
        telegram_token="your_telegram_token",
    )
    await agent.join(team)
    ```
"""

from .telegram_agent import TelegramAIAgent

__all__ = ["TelegramAIAgent"]
