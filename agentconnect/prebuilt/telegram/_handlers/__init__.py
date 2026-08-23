"""
Telegram message handlers package.

This package contains all the handlers for Telegram messages.
"""

from typing import Dict, Callable, List

from aiogram import Dispatcher

from agentconnect.prebuilt.telegram._handlers.base_handler import BaseHandler
from agentconnect.prebuilt.telegram._handlers.command_handlers import CommandHandler
from agentconnect.prebuilt.telegram._handlers.group_handlers import GroupHandler
from agentconnect.prebuilt.telegram._handlers.media_handlers import MediaHandler
from agentconnect.prebuilt.telegram._handlers.text_handlers import TextHandler


class HandlerRegistry:
    """
    Registry for Telegram message handlers.

    This class manages all the handlers for Telegram messages.
    """

    def __init__(self):
        """Initialize the handler registry."""
        self.handlers: List[BaseHandler] = [
            CommandHandler(),
            GroupHandler(),
            MediaHandler(),
            TextHandler(),
        ]

    async def register_all(
        self, dp: Dispatcher, callback_map: Dict[str, Callable]
    ) -> None:
        """
        Register all handlers with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """
        for handler in self.handlers:
            await handler.register(dp, callback_map)
