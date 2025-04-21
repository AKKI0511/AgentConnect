"""
Message processor for Telegram messages.

This module contains the message processor class that handles the processing
of Telegram messages through the AgentConnect framework.
"""

import logging
from typing import Dict, Any, Optional

from aiogram import types
from langchain_core.messages import HumanMessage

from agentconnect.core.message import Message
from agentconnect.core.types import AgentIdentity, MessageType
from agentconnect.agents.telegram._utils.message_utils import (
    get_telegram_conversation_id,
    remove_bot_mention_from_text,
)
from agentconnect.agents.telegram.bot_manager import TelegramBotManager
from agentconnect.utils.interaction_control import InteractionControl
from langchain_core.runnables import Runnable

logger = logging.getLogger(__name__)


class TelegramMessageProcessor:
    """
    Processor for Telegram messages.

    This class handles the processing of Telegram messages through the
    AgentConnect framework and sending responses back to Telegram.
    It also supports handling collaboration requests from other agents.
    """

    def __init__(
        self, agent_id: str, identity: AgentIdentity, bot_manager: TelegramBotManager
    ):
        """
        Initialize the message processor.

        Args:
            agent_id: AgentConnect agent ID
            identity: AgentConnect agent identity
            bot_manager: Telegram bot manager
        """
        self.agent_id = agent_id
        self.identity = identity
        self.bot_manager = bot_manager

    async def process_group_mention(self, message: types.Message):
        """
        Process a group mention.

        Args:
            message: Telegram message
        """
        # Log the incoming message
        logger.info(
            f"Handling group mention from {message.from_user.first_name} in chat {message.chat.title}"
        )

        # Add group to registered list if needed
        if message.chat.id not in self.bot_manager.group_ids:
            self.bot_manager.group_ids.add(message.chat.id)
            if self.bot_manager.telegram_tools:
                self.bot_manager.telegram_tools.group_ids = self.bot_manager.group_ids
                self.bot_manager.telegram_tools._save_group_ids()
            logger.info(
                f"📌 Group added through mention: {message.chat.title} ({message.chat.id})"
            )

        # Send a "thinking" message as a reply to the original message
        thinking_message = await message.reply("🤔 Thinking...")
        self.bot_manager.processing_messages[message.chat.id] = (
            thinking_message.message_id
        )

        # Create clean content by removing bot mentions
        content = message.text or ""
        if self.bot_manager.me and self.bot_manager.me.username and content:
            content = remove_bot_mention_from_text(
                content, self.bot_manager.me.username
            )

        # If content is empty after removing mention, treat as a greeting
        if not content:
            content = "Hello"

        # Create message metadata
        metadata = {
            "telegram_user_id": str(message.from_user.id),
            "telegram_chat_id": str(message.chat.id),
            "is_telegram_message": True,
            "is_group_mention": True,
            "reply_to_message_id": message.message_id,
            "group_name": message.chat.title,
            "from_username": message.from_user.username,
            "from_first_name": message.from_user.first_name,
            "context_type": "group_mention",
        }

        # Add reply context if this is a reply to another message
        if message.reply_to_message:
            metadata["original_reply_to_message_id"] = (
                message.reply_to_message.message_id
            )
            if message.reply_to_message.text:
                reply_text = message.reply_to_message.text
                content = f'{content}\n[This was sent in reply to: "{reply_text}"]'
                metadata["reply_text"] = reply_text

        # Process the message and return the AgentConnect message
        return self._create_agentconnect_message(content, metadata)

    async def process_media_message(self, message: types.Message, media_type: str):
        """
        Process a media message.

        Args:
            message: Telegram message
            media_type: Type of media
        """
        # Skip messages without user
        if not message.from_user:
            logger.info(f"Skipping message without user: {message}")
            return None

        # Send "thinking" message to indicate we're processing
        thinking_message = await message.answer("🤔 Processing your media content...")

        # Store this message ID so we can delete it later
        self.bot_manager.processing_messages[message.chat.id] = (
            thinking_message.message_id
        )

        # Create message content based on media type
        content_text = ""
        metadata = {
            "telegram_user_id": str(message.from_user.id),
            "telegram_chat_id": str(message.chat.id),
            "is_telegram_message": True,
            "media_type": media_type,
            "has_caption": message.caption is not None,
            "context_type": (
                "private_chat" if message.chat.type == "private" else "group_mention"
            ),
        }

        # Add information based on media type
        if media_type == "photo":
            # Get the highest quality photo (last in array)
            photo = message.photo[-1]
            file_id = photo.file_id
            metadata["file_id"] = file_id
            metadata["file_size"] = photo.file_size
            content_text = "[The user sent a photo"
            if message.caption:
                content_text += f' with caption: "{message.caption}"'
                metadata["caption"] = message.caption
            content_text += f". You can use the file_id: {file_id} in your tools to process it further.]"

        elif media_type == "document":
            file_id = message.document.file_id
            metadata["file_id"] = file_id
            metadata["file_size"] = message.document.file_size
            metadata["mime_type"] = message.document.mime_type
            metadata["file_name"] = message.document.file_name
            content_text = (
                f'[The user sent a document named "{message.document.file_name}"'
            )
            if message.caption:
                content_text += f' with caption: "{message.caption}"'
                metadata["caption"] = message.caption
            content_text += f". You can use the file_id: {file_id} in your tools to process it further.]"

        elif media_type == "voice":
            file_id = message.voice.file_id
            metadata["file_id"] = file_id
            metadata["duration"] = message.voice.duration
            metadata["mime_type"] = message.voice.mime_type
            content_text = (
                f"[The user sent a voice message ({message.voice.duration} seconds). "
            )
            content_text += f"You can use the file_id: {file_id} in your tools to process it further.]"

        elif media_type == "audio":
            file_id = message.audio.file_id
            metadata["file_id"] = file_id
            metadata["duration"] = message.audio.duration
            metadata["performer"] = message.audio.performer
            metadata["title"] = message.audio.title
            metadata["mime_type"] = message.audio.mime_type
            content_text = "[The user sent an audio file"
            if message.audio.title:
                content_text += f' titled "{message.audio.title}"'
            if message.audio.performer:
                content_text += f' by "{message.audio.performer}"'
            content_text += f". You can use the file_id: {file_id} in your tools to process it further.]"

        elif media_type == "location":
            metadata["latitude"] = message.location.latitude
            metadata["longitude"] = message.location.longitude
            content_text = f"[The user shared a location at latitude: {message.location.latitude}, longitude: {message.location.longitude}]"

        elif media_type == "video":
            file_id = message.video.file_id
            metadata["file_id"] = file_id
            metadata["duration"] = message.video.duration
            metadata["width"] = message.video.width
            metadata["height"] = message.video.height
            metadata["mime_type"] = message.video.mime_type
            content_text = "[The user sent a video"
            if message.caption:
                content_text += f' with caption: "{message.caption}"'
                metadata["caption"] = message.caption
            content_text += f". You can use the file_id: {file_id} in your tools to process it further.]"

        elif media_type == "sticker":
            file_id = message.sticker.file_id
            metadata["file_id"] = file_id
            metadata["emoji"] = message.sticker.emoji
            metadata["is_animated"] = message.sticker.is_animated
            metadata["is_video"] = message.sticker.is_video
            content_text = "[The user sent a sticker"
            if message.sticker.emoji:
                content_text += f" with emoji: {message.sticker.emoji}"
            content_text += "]"

        # Add reply context if this is a reply to another message
        if message.reply_to_message:
            metadata["reply_to_message_id"] = message.reply_to_message.message_id
            reply_text = (
                message.reply_to_message.text
                or message.reply_to_message.caption
                or "[non-text content]"
            )
            content_text += f'\n[This was sent in reply to: "{reply_text}"]'

        # Process the message and return the AgentConnect message
        return self._create_agentconnect_message(content_text, metadata)

    async def process_text_message(self, message: types.Message):
        """
        Process a text message.

        Args:
            message: Telegram message
        """
        # Skip messages without user
        if not message.from_user:
            logger.info(f"Skipping message without user: {message}")
            return None

        # Only proceed for text messages (media is handled separately)
        if not message.text and not hasattr(message, "media_group_id"):
            logger.debug(f"Skipping non-text message that isn't media group: {message}")
            return None

        # Send "thinking" message to indicate we're processing
        thinking_message = await message.answer("🤔 Thinking...")

        # Store this message ID so we can delete it later
        self.bot_manager.processing_messages[message.chat.id] = (
            thinking_message.message_id
        )

        # Create message content and metadata
        content = message.text or ""
        metadata = {
            "telegram_user_id": str(message.from_user.id),
            "telegram_chat_id": str(message.chat.id),
            "is_telegram_message": True,
            "context_type": (
                "private_chat" if message.chat.type == "private" else "group_chat"
            ),
        }

        # Add reply context if this is a reply to another message
        if message.reply_to_message:
            metadata["reply_to_message_id"] = message.reply_to_message.message_id
            # Check if the reply target has text content
            if message.reply_to_message.text:
                reply_text = message.reply_to_message.text
                content = f'{content}\n[This was sent in reply to: "{reply_text}"]'
                metadata["reply_text"] = reply_text
            # If reply target has caption instead (e.g., photo caption)
            elif message.reply_to_message.caption:
                reply_caption = message.reply_to_message.caption
                content = f'{content}\n[This was sent in reply to a media with caption: "{reply_caption}"]'
                metadata["reply_caption"] = reply_caption
            # If reply target has media
            elif message.reply_to_message.photo:
                content = f"{content}\n[This was sent in reply to a photo]"
                metadata["reply_media_type"] = "photo"
                # Get the highest quality photo (last in array)
                reply_photo = message.reply_to_message.photo[-1]
                metadata["reply_file_id"] = reply_photo.file_id
            elif message.reply_to_message.document:
                doc = message.reply_to_message.document
                content = f'{content}\n[This was sent in reply to a document named "{doc.file_name}"]'
                metadata["reply_media_type"] = "document"
                metadata["reply_file_id"] = doc.file_id
                metadata["reply_file_name"] = doc.file_name
            else:
                content = f"{content}\n[This was sent in reply to a previous message]"

        # Process the message and return the AgentConnect message
        return self._create_agentconnect_message(content, metadata)

    def _create_agentconnect_message(
        self, content: str, metadata: Dict[str, Any]
    ) -> Message:
        """
        Create an AgentConnect message from Telegram message content and metadata.

        Args:
            content: Message content
            metadata: Message metadata

        Returns:
            AgentConnect message
        """
        return Message.create(
            sender_id=self.agent_id,
            receiver_id=self.agent_id,
            content=content,
            sender_identity=self.identity,
            message_type=MessageType.TEXT,
            metadata=metadata,
        )

    async def process_agent_response(
        self,
        workflow: Runnable,
        message: Message,
        interaction_control: InteractionControl,
    ) -> Optional[Dict[str, Any]]:
        """
        Process an AgentConnect message through the agent workflow.

        Args:
            workflow: Agent workflow
            message: AgentConnect message
            interaction_control: Interaction control for token counting

        Returns:
            Response details or None if processing failed
        """
        try:
            # Get the conversation ID for this message
            conversation_id = get_telegram_conversation_id(message.metadata)

            # Create the initial state for the workflow
            initial_state = {
                "messages": [HumanMessage(content=message.content)],
                "sender": self.agent_id,
                "receiver": self.agent_id,
                "message_type": message.message_type.value,
                "metadata": message.metadata,
            }

            # Set up the configuration for the workflow
            config = {
                "configurable": {
                    "thread_id": conversation_id,
                },
                "callbacks": interaction_control.get_callback_handlers(),
            }

            logger.debug(
                f"Processing Telegram message with conversation ID: {conversation_id}"
            )

            # Process with our workflow (which includes Telegram tools)
            response = await workflow.ainvoke(initial_state, config)

            # Extract the last message from the response
            last_message = response["messages"][-1]

            # Check if we should reply to a message ID
            reply_to_message_id = None
            if message.metadata.get("reply_to_message_id"):
                # If original message was a reply, we'll reply to the same message
                reply_to_message_id = message.metadata.get("reply_to_message_id")

            return {
                "content": last_message.content,
                "chat_id": int(message.metadata.get("telegram_chat_id")),
                "reply_to_message_id": reply_to_message_id,
            }

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return None
