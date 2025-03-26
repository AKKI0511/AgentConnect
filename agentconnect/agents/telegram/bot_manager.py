"""
Telegram bot lifecycle manager.

This module handles the initialization, startup, and shutdown of the Telegram bot,
providing a clean interface for the agent to interact with the bot.
"""

import asyncio
import logging
from typing import Dict, Optional, Set, Callable, Any

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from agentconnect.agents.telegram._utils.file_utils import (
    load_group_ids,
    save_group_ids,
)
from agentconnect.agents.telegram.telegram_tools import TelegramTools

logger = logging.getLogger(__name__)


class TelegramBotManager:
    """
    Manager for Telegram bot lifecycle and core functionality.

    This class handles the initialization, startup, and shutdown of the Telegram bot,
    and provides methods for interacting with the bot.
    """

    def __init__(self, token: str, groups_file: str):
        """
        Initialize the bot manager.

        Args:
            token: Telegram bot token from BotFather
            groups_file: Path to the file storing group IDs
        """
        self.token = token
        self.groups_file = groups_file
        self.group_ids: Set[int] = load_group_ids(groups_file)

        # Telegram components
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.me: Optional[types.User] = None
        self.telegram_tools: Optional[TelegramTools] = None
        self.telegram_polling_task: Optional[asyncio.Task] = None

        # Message processing tracking
        self.processing_messages: Dict[int, int] = {}

    def initialize_bot(self) -> bool:
        """
        Initialize the bot and dispatcher.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Initialize bot with HTML parse mode
            self.bot = Bot(
                token=self.token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            logger.debug("Bot instance created")

            # Initialize dispatcher with FSM storage
            storage = MemoryStorage()
            self.dp = Dispatcher(storage=storage)
            logger.debug("Dispatcher initialized with memory storage")

            # Set default me value (will be updated later when bot starts)
            self.me = None

            return True
        except Exception as e:
            logger.exception(f"Error initializing Telegram bot: {e}")
            self.bot = None
            self.dp = None
            return False

    def initialize_tools(self) -> bool:
        """
        Initialize Telegram-specific tools.

        Returns:
            True if initialization was successful, False otherwise
        """
        if self.bot:
            try:
                self.telegram_tools = TelegramTools(
                    bot=self.bot,
                    group_ids=self.group_ids,
                    groups_file=self.groups_file,
                )
                logger.debug("Telegram tools initialized")
                return True
            except Exception as e:
                logger.exception(f"Error initializing Telegram tools: {e}")
                return False
        else:
            logger.warning("Cannot initialize Telegram tools - bot not initialized")
            return False

    def register_shutdown_handler(self, callback: Callable) -> None:
        """
        Register a shutdown handler with the dispatcher.

        Args:
            callback: Async function to call on shutdown
        """
        if self.dp:
            self.dp.shutdown.register(callback)
            logger.debug("Shutdown handler registered")
        else:
            logger.warning(
                "Cannot register shutdown handler - dispatcher not initialized"
            )

    async def start_polling(self) -> bool:
        """
        Start the bot polling.

        Returns:
            True if polling started successfully, False otherwise
        """
        if not self.bot or not self.dp:
            logger.error("Cannot start polling - bot or dispatcher not initialized")
            return False

        try:
            # First delete webhook to ensure no duplicate messages
            await self.bot.delete_webhook(drop_pending_updates=True)

            # CRITICAL: Get bot info FIRST before doing anything else
            self.me = await self.bot.get_me()
            if not self.me or not self.me.username:
                logger.error(
                    "Failed to get bot username! Mention detection won't work properly."
                )
                return False
            else:
                logger.info(
                    f"Retrieved bot info: @{self.me.username} (ID: {self.me.id})"
                )
                logger.info(
                    f"🤖 Bot is ready! You can mention me in groups as @{self.me.username}"
                )

            # Start polling
            logger.info("Starting Telegram bot polling...")
            self.telegram_polling_task = asyncio.create_task(
                self.dp.start_polling(self.bot)
            )
            return True
        except Exception as e:
            logger.exception(f"Error starting Telegram bot polling: {e}")
            return False

    async def stop_polling(self) -> None:
        """Stop the bot polling and clean up resources."""
        if self.telegram_polling_task:
            logger.info("Stopping Telegram bot polling...")
            self.telegram_polling_task.cancel()
            try:
                await self.telegram_polling_task
            except asyncio.CancelledError:
                pass
            finally:
                # Save group IDs before stopping
                if self.telegram_tools:
                    save_group_ids(self.groups_file, self.group_ids)

                if self.bot:
                    await self.bot.session.close()
                    self.bot = None
                self.dp = None
                self.telegram_polling_task = None
                logger.info("Telegram bot polling stopped.")

    async def send_message(
        self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            text: Text to send
            reply_to_message_id: Optional message ID to reply to

        Returns:
            Dict with success status and message ID or error
        """
        if not self.bot:
            logger.error("Cannot send message - bot not initialized")
            return {"success": False, "error": "Bot not initialized"}

        # First, delete the "thinking" message if it exists
        try:
            if chat_id in self.processing_messages:
                try:
                    await self.bot.delete_message(
                        chat_id=chat_id, message_id=self.processing_messages[chat_id]
                    )
                except Exception as e:
                    logger.error(f"Error deleting thinking message: {e}")
                # Always remove from dictionary even if deletion failed
                del self.processing_messages[chat_id]
        except Exception as e:
            logger.error(f"Error handling processing messages cleanup: {e}")

        # Handle large messages (Telegram limit is 4096 characters)
        try:
            if len(text) > 4000:
                parts = [text[i : i + 4000] for i in range(0, len(text), 4000)]
                sent_message_id = None

                for i, part in enumerate(parts):
                    if i > 0:
                        await asyncio.sleep(0.5)  # Avoid flood limits

                    # Only reply to the original message with the first part
                    send_reply_to = reply_to_message_id if i == 0 else None

                    # Add continuation marker if needed
                    part_text = part
                    if i < len(parts) - 1:
                        part_text += "\n(continued...)"

                    message = await self.bot.send_message(
                        chat_id=chat_id,
                        text=part_text,
                        reply_to_message_id=send_reply_to,
                    )

                    # Store the first message ID
                    if i == 0:
                        sent_message_id = message.message_id

                return {"success": True, "message_id": sent_message_id}
            else:
                # Single message
                message = await self.bot.send_message(
                    chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id
                )
                return {"success": True, "message_id": message.message_id}

        except Exception as e:
            logger.error(f"Error sending message to Telegram: {e}")

            # Fall back to sending without reply_to_message_id if that's the issue
            try:
                message = await self.bot.send_message(chat_id=chat_id, text=text)
                logger.info(
                    f"Sent response without reply_to_message_id to chat {chat_id}"
                )
                return {"success": True, "message_id": message.message_id}
            except Exception as e2:
                logger.error(f"Failed to send message to chat {chat_id}: {e2}")
                return {"success": False, "error": str(e2)}
