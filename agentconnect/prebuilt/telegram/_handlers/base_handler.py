"""
Base handler interface for Telegram message handlers.

This module defines the base handler interface that all Telegram message handlers must implement.
"""

import abc
from typing import Dict, Callable

from aiogram import Dispatcher


class BaseHandler(abc.ABC):
    """
    Base handler interface for Telegram message handlers.

    All handlers must implement the register method, which registers
    the handler with the Telegram dispatcher.
    """

    @abc.abstractmethod
    async def register(self, dp: Dispatcher, callback_map: Dict[str, Callable]) -> None:
        """
        Register the handler with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """
        pass
