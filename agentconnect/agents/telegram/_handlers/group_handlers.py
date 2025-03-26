"""
Group message handlers for the Telegram agent.

This module contains handlers for Telegram group messages, including
handlers for bot mentions and group management.
"""

from typing import Dict, Callable

from aiogram import Dispatcher, F, types

from agentconnect.agents.telegram._handlers.base_handler import BaseHandler


class GroupHandler(BaseHandler):
    """
    Handler for Telegram group messages.

    This handler registers handlers for group messages, including
    handlers for bot mentions and group management.
    """

    async def register(self, dp: Dispatcher, callback_map: Dict[str, Callable]) -> None:
        """
        Register group message handlers with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """

        # Group-specific handlers
        @dp.message(F.chat.type.in_({"group", "supergroup"}))
        async def handle_group_message(message: types.Message):
            """Handle messages in group chats."""
            # Extract the bot user from callbacks
            bot_user = callback_map["get_bot_user"]()

            # Check if we have bot information
            if not bot_user or not bot_user.username:
                return

            # Check for mentions in text
            if message.text and f"@{bot_user.username}" in message.text:
                await callback_map["handle_group_mention"](message)
                return

            # Check for replies to bot's messages
            if (
                message.reply_to_message
                and message.reply_to_message.from_user
                and message.reply_to_message.from_user.id == bot_user.id
            ):
                await callback_map["handle_group_mention"](message)
                return

        # View Groups button in private chats
        @dp.message(F.text == "📜 View Groups", F.chat.type == "private")
        async def handle_view_groups(message: types.Message):
            """Handle the View Groups button in private chats."""
            await callback_map["handle_view_groups"](message)

        # New Announcement button in private chats
        @dp.message(F.text == "➕ New Announcement", F.chat.type == "private")
        async def handle_new_announcement(message: types.Message):
            """Handle the New Announcement button in private chats."""
            await callback_map["handle_message"](message)
