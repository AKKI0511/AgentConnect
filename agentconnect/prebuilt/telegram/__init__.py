"""Telegram chats on an `AIAgent`.

`TelegramAIAgent` polls Telegram and answers with the same LiteLLM loop
as Team work. Team deliveries still use `handle` and `ctx.history`.
Telegram text keeps a separate history per chat, capped at 40 messages.
`run` polls until cancelled, then stops polling and writes group ids.
Call `leave` when the Team Session should close. `run` does not call it.

Set `TELEGRAM_BOT_TOKEN`, or pass `telegram_token`. Install
`agentconnect[telegram]`.

Examples:
    `team` is started and `TELEGRAM_BOT_TOKEN` is set:

    ```python
    from agentconnect.prebuilt import TelegramAIAgent

    agent = TelegramAIAgent(name="telegram-bot", model="gpt-4o-mini")
    await agent.join(team)
    await agent.run()
    ```
"""

from .telegram_agent import TelegramAIAgent

__all__ = ["TelegramAIAgent"]
