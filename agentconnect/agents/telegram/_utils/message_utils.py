"""
Utility functions for processing Telegram messages.

This module contains helper functions for working with Telegram messages,
including checking for mentions, extracting content, and managing conversation IDs.
"""

import logging
from typing import Dict, Any

from aiogram import types
from aiogram.types import User

logger = logging.getLogger(__name__)


def has_mention_entity(message: types.Message, bot_user: User) -> bool:
    """
    Check if the message entities contain a mention of the bot.

    Args:
        message: The message to check
        bot_user: The bot's user information

    Returns:
        True if any entity is a mention of the bot, False otherwise
    """
    if not bot_user or not bot_user.username:
        return False

    if not message.entities:
        return False

    for entity in message.entities:
        if entity.type == "mention" and entity.offset + entity.length <= len(
            message.text or ""
        ):
            try:
                mention_text = message.text[
                    entity.offset : entity.offset + entity.length
                ]
                if mention_text.lower() == f"@{bot_user.username.lower()}":
                    return True
            except (IndexError, AttributeError):
                continue

    return False


def has_bot_mention(message: types.Message, bot_user: User) -> bool:
    """
    Check if the message text contains the bot's username mention.

    Args:
        message: The message to check
        bot_user: The bot's user information

    Returns:
        True if the message text contains the bot's username, False otherwise
    """
    if not message.text or not bot_user or not bot_user.username:
        return False

    # Case insensitive check
    return f"@{bot_user.username.lower()}" in message.text.lower()


def is_bot_mentioned(message: types.Message, bot_user: User) -> bool:
    """
    Comprehensive check if the bot is mentioned in a message.

    Args:
        message: The message to check
        bot_user: The bot's user information

    Returns:
        True if the bot is mentioned, False otherwise
    """
    if not bot_user:
        return False

    # Text mentions (like @bot_name)
    if message.text and has_bot_mention(message, bot_user):
        return True

    # Entity mentions
    if message.entities and has_mention_entity(message, bot_user):
        return True

    # Check for direct reply to bot's message
    if (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot_user.id
    ):
        return True

    return False


def remove_bot_mention_from_text(text: str, bot_username: str) -> str:
    """
    Remove the bot mention from the message text.

    Args:
        text: The message text
        bot_username: The bot's username

    Returns:
        Text with bot mention removed
    """
    if not text or not bot_username:
        return text or ""

    mention = f"@{bot_username}"
    return text.replace(mention, "").strip()


def get_telegram_conversation_id(metadata: Dict[str, Any]) -> str:
    """
    Generate a unique conversation ID for Telegram conversations based on context.

    This ensures different contexts (private chat, group mention, etc.) have separate conversation histories.

    Args:
        metadata: The message metadata containing Telegram-specific information

    Returns:
        A unique conversation ID string
    """
    user_id = metadata.get("telegram_user_id", "unknown")
    chat_id = metadata.get("telegram_chat_id", "unknown")
    context_type = metadata.get("context_type", "private_chat")

    # For private chats (direct messages to the bot)
    if context_type == "private_chat":
        return f"telegram_private_{user_id}"

    # For group mentions (when bot is mentioned in a group)
    elif context_type == "group_mention":
        # Use both group ID and user ID to isolate conversations per user per group
        return f"telegram_group_{chat_id}_user_{user_id}"

    # For media messages
    elif metadata.get("media_type"):
        # If it's a private chat with media
        if context_type == "private_chat":
            return f"telegram_private_{user_id}"
        # If it's a group media message with mention
        else:
            return f"telegram_group_{chat_id}_user_{user_id}"

    # Default fallback with unique combination
    return f"telegram_{context_type}_{chat_id}_{user_id}"
