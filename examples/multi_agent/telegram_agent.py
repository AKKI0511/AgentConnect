"""Telegram bot on the same Team as the other demo agents."""

from __future__ import annotations

from typing import Any

from agentconnect.prebuilt import TelegramAIAgent


def create_telegram_agent(
    model: str, telegram_token: str, **kwargs: Any
) -> TelegramAIAgent:
    """Return a Telegram member. Requires ``agentconnect[telegram]``."""
    return TelegramAIAgent(
        name="telegram-bot",
        model=model,
        telegram_token=telegram_token,
        instructions=(
            "You are the Telegram door for this Team. For Team work, find a "
            "teammate and ask them. For Telegram users, reply in the chat."
        ),
        **kwargs,
    )
