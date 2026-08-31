"""Telegram Agent for AgentConnect.

``TelegramAIAgent`` extends ``AIAgent`` with a Telegram bot. Join a Team,
then ``run()`` to poll.

    from agentconnect.prebuilt import TelegramAIAgent
    from agentconnect.team import Team

    agent = TelegramAIAgent(
        name="telegram-bot",
        model="gpt-4o-mini",
        telegram_token="your_telegram_token",
    )
    team = await Team("content-squad").start()
    await agent.join(team)
    await agent.run()
"""

from .telegram_agent import TelegramAIAgent

__all__ = ["TelegramAIAgent"]
