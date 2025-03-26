"""
Media message handlers for the Telegram agent.

This module contains handlers for Telegram media messages, including
photos, documents, voice messages, and other media types.
"""

from typing import Dict, Callable

from aiogram import Dispatcher, F, types

from agentconnect.agents.telegram._handlers.base_handler import BaseHandler


class MediaHandler(BaseHandler):
    """
    Handler for Telegram media messages.

    This handler registers handlers for media messages, including
    photos, documents, voice messages, and other media types.
    """

    async def register(self, dp: Dispatcher, callback_map: Dict[str, Callable]) -> None:
        """
        Register media message handlers with the Telegram dispatcher.

        Args:
            dp: Telegram dispatcher
            callback_map: Map of callback names to callback functions
        """

        # Media message handlers for private chats
        @dp.message(F.photo, F.chat.type == "private")
        async def handle_private_photo(message: types.Message):
            """Handle photo messages in private chats."""
            await callback_map["handle_media_message"](message, "photo")

        @dp.message(F.document, F.chat.type == "private")
        async def handle_private_document(message: types.Message):
            """Handle document messages in private chats."""
            await callback_map["handle_media_message"](message, "document")

        @dp.message(F.voice, F.chat.type == "private")
        async def handle_private_voice(message: types.Message):
            """Handle voice messages in private chats."""
            await callback_map["handle_media_message"](message, "voice")

        @dp.message(F.audio, F.chat.type == "private")
        async def handle_private_audio(message: types.Message):
            """Handle audio messages in private chats."""
            await callback_map["handle_media_message"](message, "audio")

        @dp.message(F.location, F.chat.type == "private")
        async def handle_private_location(message: types.Message):
            """Handle location messages in private chats."""
            await callback_map["handle_media_message"](message, "location")

        @dp.message(F.video, F.chat.type == "private")
        async def handle_private_video(message: types.Message):
            """Handle video messages in private chats."""
            await callback_map["handle_media_message"](message, "video")

        @dp.message(F.sticker, F.chat.type == "private")
        async def handle_private_sticker(message: types.Message):
            """Handle sticker messages in private chats."""
            await callback_map["handle_media_message"](message, "sticker")
