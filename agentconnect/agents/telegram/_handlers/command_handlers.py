"""
Command message handlers for the Telegram agent.

This module contains handlers for Telegram command messages, like /start and /help.
"""

from typing import Dict, Callable

from aiogram import Dispatcher, F, types
from aiogram.filters import CommandStart, Command

from agentconnect.agents.telegram._handlers.base_handler import BaseHandler
from agentconnect.agents.telegram.keyboards import (
    PRIVATE_CHAT_KEYBOARD,
    GROUP_CHAT_KEYBOARD,
)


class CommandHandler(BaseHandler):
    """
    Handler for Telegram command messages.

    This handler registers handlers for the /start and /help commands,
    as well as the Help and About buttons.
    """

    async def register(self, dp: Dispatcher, callback_map: Dict[str, Callable]) -> None:
        """
        Register command handlers with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """

        # Command handlers
        @dp.message(CommandStart())
        async def handle_start(message: types.Message):
            """Handler for the /start command."""
            await callback_map["handle_start"](message)

        @dp.message(Command(commands=["help"]))
        async def handle_help(message: types.Message):
            """Handler for the /help command."""
            await callback_map["handle_help"](message)

        @dp.message(F.text == "💡 Help")
        async def handle_help_button(message: types.Message):
            """Handle the Help button."""
            help_text = callback_map["get_help_text"]()
            # Choose the appropriate keyboard based on chat type
            keyboard = (
                PRIVATE_CHAT_KEYBOARD
                if message.chat.type == "private"
                else GROUP_CHAT_KEYBOARD
            )
            await message.answer(help_text, reply_markup=keyboard)

        @dp.message(F.text == "🤖 About")
        async def handle_about(message: types.Message):
            """Handle the About button."""
            await callback_map["handle_about"](message)
