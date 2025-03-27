"""
Text message handlers for the Telegram agent.

This module contains handlers for Telegram text messages in private chats.
"""

from typing import Dict, Callable

from aiogram import Dispatcher, F, types

from agentconnect.agents.telegram._handlers.base_handler import BaseHandler


class TextHandler(BaseHandler):
    """
    Handler for Telegram text messages.

    This handler registers handlers for text messages in private chats.
    """

    async def register(self, dp: Dispatcher, callback_map: Dict[str, Callable]) -> None:
        """
        Register text message handlers with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """

        # Catch-all for text messages in private chats
        @dp.message(F.chat.type == "private")
        async def handle_private_text(message: types.Message):
            """Handle text messages in private chats."""
            await callback_map["handle_message"](message)
