"""
Base handler interface for Telegram message handlers.

This module defines the base handler interface that all Telegram message handlers must implement.
"""

import abc
from collections.abc import Awaitable, Callable
from typing import TypedDict

from aiogram import Dispatcher, types


class _HandlerCallbacks(TypedDict):
    handle_start: Callable[[types.Message], Awaitable[None]]
    handle_help: Callable[[types.Message], Awaitable[None]]
    handle_about: Callable[[types.Message], Awaitable[None]]
    handle_view_groups: Callable[[types.Message], Awaitable[None]]
    handle_group_mention: Callable[[types.Message], Awaitable[None]]
    handle_media_message: Callable[[types.Message, str], Awaitable[None]]
    handle_message: Callable[[types.Message], Awaitable[None]]
    get_help_text: Callable[[], str]
    get_bot_user: Callable[[], types.User | None]


class BaseHandler(abc.ABC):
    """
    Base handler interface for Telegram message handlers.

    All handlers must implement the register method, which registers
    the handler with the Telegram dispatcher.
    """

    @abc.abstractmethod
    async def register(self, dp: Dispatcher, callback_map: _HandlerCallbacks) -> None:
        """
        Register the handler with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """
        pass
