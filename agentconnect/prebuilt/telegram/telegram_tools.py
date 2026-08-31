"""
Telegram-specific tools for use with the AgentConnect framework.

This module defines tools that enable an AI agent to interact with Telegram,
manage announcements, handle user groups, and send messages using advanced
aiogram v3 capabilities.
"""

import asyncio
import logging
import os
import uuid
from typing import Dict, List, Optional, Set, Any

from aiogram import Bot
from aiogram.types import FSInputFile, URLInputFile
from aiogram.enums import ParseMode
from pydantic import BaseModel, Field

from agentconnect.prebuilt.tools import Tool

logger = logging.getLogger(__name__)

# Input/Output schemas for Telegram tools


class SendMessageInput(BaseModel):
    """Input schema for sending a message to Telegram."""

    chat_id: int = Field(
        description="Telegram chat ID to send the message to. IMPORTANT: This must be a DIFFERENT chat than the one you're currently responding to. DO NOT use this for normal responses."
    )
    text: str = Field(description="Text message to send to the different chat")
    reply_to_message_id: Optional[int] = Field(
        None, description="Optional message ID to reply to within that chat"
    )
    parse_mode: Optional[str] = Field(
        None,
        description="Parse mode for the message, if different from default (HTML, Markdown, or None)",
    )


class SendMessageOutput(BaseModel):
    """Output schema for sending a message to Telegram."""

    success: bool = Field(description="Whether the message was sent successfully")
    message_id: Optional[int] = Field(
        default=None, description="ID of the sent message"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if sending failed"
    )


class SendPhotoInput(BaseModel):
    """Input schema for sending a photo to Telegram."""

    chat_id: int = Field(description="Telegram chat ID to send the photo to")
    photo_url: str = Field(description="URL or file_id of the photo to send")
    caption: Optional[str] = Field(None, description="Optional caption for the photo")
    reply_to_message_id: Optional[int] = Field(
        None, description="Optional message ID to reply to"
    )


class SendPhotoOutput(BaseModel):
    """Output schema for sending a photo to Telegram."""

    success: bool = Field(description="Whether the photo was sent successfully")
    message_id: Optional[int] = Field(
        default=None, description="ID of the sent message"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if sending failed"
    )


class SendDocumentInput(BaseModel):
    """Input schema for sending a document to Telegram."""

    chat_id: int = Field(description="Telegram chat ID to send the document to")
    document_url: str = Field(description="URL or file_id of the document to send")
    caption: Optional[str] = Field(
        None, description="Optional caption for the document"
    )
    reply_to_message_id: Optional[int] = Field(
        None, description="Optional message ID to reply to"
    )


class SendDocumentOutput(BaseModel):
    """Output schema for sending a document to Telegram."""

    success: bool = Field(description="Whether the document was sent successfully")
    message_id: Optional[int] = Field(
        default=None, description="ID of the sent message"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if sending failed"
    )


class SendLocationInput(BaseModel):
    """Input schema for sending a location to Telegram."""

    chat_id: int = Field(description="Telegram chat ID to send the location to")
    latitude: float = Field(description="Latitude of the location")
    longitude: float = Field(description="Longitude of the location")
    reply_to_message_id: Optional[int] = Field(
        None, description="Optional message ID to reply to"
    )


class SendLocationOutput(BaseModel):
    """Output schema for sending a location to Telegram."""

    success: bool = Field(description="Whether the location was sent successfully")
    message_id: Optional[int] = Field(
        default=None, description="ID of the sent message"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if sending failed"
    )


class SendVoiceInput(BaseModel):
    """Input schema for sending a voice message to Telegram."""

    chat_id: int = Field(description="Telegram chat ID to send the voice to")
    voice_url: str = Field(description="URL or file_id of the voice to send")
    caption: Optional[str] = Field(
        None, description="Optional caption for the voice message"
    )
    reply_to_message_id: Optional[int] = Field(
        None, description="Optional message ID to reply to"
    )


class SendVoiceOutput(BaseModel):
    """Output schema for sending a voice message to Telegram."""

    success: bool = Field(description="Whether the voice was sent successfully")
    message_id: Optional[int] = Field(
        default=None, description="ID of the sent message"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if sending failed"
    )


class DownloadFileInput(BaseModel):
    """Input schema for downloading a file from Telegram."""

    file_id: str = Field(description="Telegram file ID to download")


class DownloadFileOutput(BaseModel):
    """Output schema for downloading a file from Telegram."""

    success: bool = Field(description="Whether the file was downloaded successfully")
    file_path: Optional[str] = Field(
        default=None, description="Local path where the file was saved"
    )
    content_type: Optional[str] = Field(
        default=None, description="Content type of the file"
    )
    file_size: Optional[int] = Field(
        default=None, description="Size of the file in bytes"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if download failed"
    )


class CreateAnnouncementInput(BaseModel):
    """Input schema for creating an announcement."""

    text: str = Field(description="Announcement text content")
    photo_url: str = Field(
        default="",
        description="URL or file_id for an announcement image. Leave empty for text-only announcement.",
    )


class CreateAnnouncementOutput(BaseModel):
    """Output schema for creating an announcement."""

    announcement_id: str = Field(description="Unique ID for the created announcement")
    text: str = Field(description="Announcement text content")
    photo_url: Optional[str] = Field(
        default=None, description="URL or file_id of the photo if included"
    )


class PublishAnnouncementInput(BaseModel):
    """Input schema for publishing an announcement to groups."""

    announcement_id: str = Field(description="ID of the announcement to publish")
    groups: List[int] = Field(
        default=[],
        description="List of specific group IDs to publish to. If empty, sends to all registered groups.",
    )


class PublishAnnouncementOutput(BaseModel):
    """Output schema for publishing an announcement."""

    success: bool = Field(
        description="Whether the announcement was published successfully"
    )
    sent_to_groups: List[int] = Field(
        description="List of group IDs the announcement was sent to"
    )
    failed_groups: List[Dict[str, Any]] = Field(
        description="List of groups and errors where sending failed"
    )


class ListGroupsInput(BaseModel):
    """Input schema for listing registered groups."""

    limit: int = Field(10, description="Maximum number of groups to return")


class ListGroupsOutput(BaseModel):
    """Output schema for listing registered groups."""

    groups: List[Dict[str, Any]] = Field(
        description="List of registered groups with their IDs"
    )
    total: int = Field(description="Total number of registered groups")


class DeleteAnnouncementInput(BaseModel):
    """Input schema for deleting a draft announcement."""

    announcement_id: str = Field(description="ID of the announcement to delete")


class DeleteAnnouncementOutput(BaseModel):
    """Output schema for deleting an announcement."""

    success: bool = Field(
        description="Whether the announcement was deleted successfully"
    )
    error: Optional[str] = Field(None, description="Error message if deletion failed")


class EditMessageInput(BaseModel):
    """Input schema for editing a message."""

    chat_id: int = Field(description="Telegram chat ID where the message is")
    message_id: int = Field(description="ID of the message to edit")
    text: str = Field(description="New text for the message")


class EditMessageOutput(BaseModel):
    """Output schema for editing a message."""

    success: bool = Field(description="Whether the message was edited successfully")
    error: Optional[str] = Field(None, description="Error message if editing failed")


# Telegram Tools class


class TelegramTools:
    """
    Contains tools for interacting with Telegram through the AgentConnect framework.

    This class provides tools for sending messages, managing announcements,
    and interacting with Telegram users and groups.
    """

    def __init__(self, bot: Bot, group_ids: Set[int], groups_file: str):
        """
        Initialize Telegram tools.

        Args:
            bot: Telegram Bot instance
            group_ids: Set of registered group IDs
            groups_file: Path to file storing group IDs
        """
        self.bot = bot
        self.group_ids = group_ids
        self.groups_file = groups_file
        self.announcements: Dict[str, Dict[str, Any]] = {}
        self.announcement_counter = 0
        self.download_dir = "downloads"

        # Create download directory if it doesn't exist
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def _save_group_ids(self) -> None:
        """Save group IDs to a file."""
        try:
            with open(self.groups_file, "w") as file:
                for gid in self.group_ids:
                    file.write(f"{gid}\n")
        except IOError as e:
            logger.error(f"Error saving group IDs to {self.groups_file}: {e}")

    def _get_next_announcement_id(self) -> str:
        """Generate a unique announcement ID."""
        self.announcement_counter += 1
        return f"ann_{self.announcement_counter}"

    # Tool Implementations

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a text message to a Telegram chat.

        IMPORTANT: DO NOT USE THIS FOR RESPONDING TO THE USER WHO SENT THE CURRENT MESSAGE.
        This tool should ONLY be used when you need to send a message to a DIFFERENT chat/group
        than the one where the current conversation is happening.

        For normal responses to the user, just return your response text directly in your reply.

        Args:
            chat_id: Telegram chat ID to send message to (must be different from current chat)
            text: Text message to send
            reply_to_message_id: Optional message ID to reply to
            parse_mode: Parse mode for the message

        Returns:
            Dict with success status and message ID or error
        """
        try:
            # Determine parse mode to use
            effective_parse_mode = None
            if parse_mode:
                if parse_mode.upper() == "HTML":
                    effective_parse_mode = ParseMode.HTML
                elif parse_mode.upper() in ["MARKDOWN", "MD"]:
                    effective_parse_mode = ParseMode.MARKDOWN_V2

            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                parse_mode=effective_parse_mode,
            )
            return {"success": True, "message_id": message.message_id}
        except Exception:
            logger.error("Error sending message to chat_id=%s", chat_id, exc_info=True)
            return {"success": False, "error": "send_failed"}

    async def send_photo(
        self,
        chat_id: int,
        photo_url: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a photo to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            photo_url: URL or file_id of the photo
            caption: Optional caption for the photo
            reply_to_message_id: Optional message ID to reply to

        Returns:
            Dict with success status and message ID or error
        """
        try:
            # Determine if photo_url is a URL, file path, or file_id
            if photo_url.startswith(("http://", "https://")):
                photo = URLInputFile(photo_url)
            elif os.path.exists(photo_url):
                photo = FSInputFile(photo_url)
            else:
                # Assume it's a file_id
                photo = photo_url

            message = await self.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_to_message_id=reply_to_message_id,
            )
            return {"success": True, "message_id": message.message_id}
        except Exception:
            logger.error("Error sending photo to chat_id=%s", chat_id, exc_info=True)
            return {"success": False, "error": "send_photo_failed"}

    async def send_document(
        self,
        chat_id: int,
        document_url: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a document to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            document_url: URL or file_id of the document
            caption: Optional caption for the document
            reply_to_message_id: Optional message ID to reply to

        Returns:
            Dict with success status and message ID or error
        """
        try:
            # Determine if document_url is a URL, file path, or file_id
            if document_url.startswith(("http://", "https://")):
                document = URLInputFile(document_url)
            elif os.path.exists(document_url):
                document = FSInputFile(document_url)
            else:
                # Assume it's a file_id
                document = document_url

            message = await self.bot.send_document(
                chat_id=chat_id,
                document=document,
                caption=caption,
                reply_to_message_id=reply_to_message_id,
            )
            return {"success": True, "message_id": message.message_id}
        except Exception:
            logger.error("Error sending document to chat_id=%s", chat_id, exc_info=True)
            return {"success": False, "error": "send_document_failed"}

    async def send_location(
        self,
        chat_id: int,
        latitude: float,
        longitude: float,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a location to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            latitude: Latitude of the location
            longitude: Longitude of the location
            reply_to_message_id: Optional message ID to reply to

        Returns:
            Dict with success status and message ID or error
        """
        try:
            message = await self.bot.send_location(
                chat_id=chat_id,
                latitude=latitude,
                longitude=longitude,
                reply_to_message_id=reply_to_message_id,
            )
            return {"success": True, "message_id": message.message_id}
        except Exception:
            logger.error("Error sending location to chat_id=%s", chat_id, exc_info=True)
            return {"success": False, "error": "send_location_failed"}

    async def send_voice(
        self,
        chat_id: int,
        voice_url: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a voice message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            voice_url: URL or file_id of the voice
            caption: Optional caption for the voice message
            reply_to_message_id: Optional message ID to reply to

        Returns:
            Dict with success status and message ID or error
        """
        try:
            # Determine if voice_url is a URL, file path, or file_id
            if voice_url.startswith(("http://", "https://")):
                voice = URLInputFile(voice_url)
            elif os.path.exists(voice_url):
                voice = FSInputFile(voice_url)
            else:
                # Assume it's a file_id
                voice = voice_url

            message = await self.bot.send_voice(
                chat_id=chat_id,
                voice=voice,
                caption=caption,
                reply_to_message_id=reply_to_message_id,
            )
            return {"success": True, "message_id": message.message_id}
        except Exception:
            logger.error("Error sending voice to chat_id=%s", chat_id, exc_info=True)
            return {"success": False, "error": "send_voice_failed"}

    async def download_file(self, file_id: str) -> Dict[str, Any]:
        """
        Download a file from Telegram.

        Args:
            file_id: Telegram file ID

        Returns:
            Dict with download information
        """
        try:
            # Get file info
            file_info = await self.bot.get_file(file_id)

            # Generate a unique filename
            file_ext = (
                os.path.splitext(file_info.file_path)[1] if file_info.file_path else ""
            )
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            local_path = os.path.join(self.download_dir, unique_filename)

            # Download the file
            await self.bot.download_file(file_info.file_path, local_path)

            return {
                "success": True,
                "file_path": local_path,
                "content_type": (
                    file_info.mime_type if hasattr(file_info, "mime_type") else None
                ),
                "file_size": (
                    file_info.file_size if hasattr(file_info, "file_size") else None
                ),
            }
        except Exception:
            logger.error("Error downloading file file_id=%s", file_id, exc_info=True)
            return {"success": False, "error": "download_failed"}

    async def edit_message(
        self, chat_id: int, message_id: int, text: str
    ) -> Dict[str, Any]:
        """
        Edit an existing message.

        Args:
            chat_id: Telegram chat ID
            message_id: ID of the message to edit
            text: New text for the message

        Returns:
            Dict with success status or error
        """
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text
            )
            return {"success": True}
        except Exception:
            logger.error("Error editing message in chat_id=%s", chat_id, exc_info=True)
            return {"success": False, "error": "edit_failed"}

    async def create_announcement(
        self, text: str, photo_url: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new announcement.

        Args:
            text: Announcement text content
            photo_url: URL or file_id for an announcement image. Empty string for text-only announcement.

        Returns:
            Dict with announcement details
        """
        announcement_id = self._get_next_announcement_id()

        # Only include photo_url in the announcement if it's not empty
        photo_url_value = photo_url if photo_url else None

        announcement = {
            "id": announcement_id,
            "text": text,
            "photo_url": photo_url_value,
            "created_at": asyncio.get_event_loop().time(),
        }

        self.announcements[announcement_id] = announcement

        return {
            "announcement_id": announcement_id,
            "text": text,
            "photo_url": photo_url_value,
        }

    async def publish_announcement(
        self, announcement_id: str, groups: List[int] = None
    ) -> Dict[str, Any]:
        """
        Publish an announcement to groups.

        Args:
            announcement_id: ID of the announcement to publish
            groups: List of specific group IDs to publish to. If empty, publishes to all groups.

        Returns:
            Dict with publishing results
        """
        if announcement_id not in self.announcements:
            return {
                "success": False,
                "error": f"Announcement {announcement_id} not found",
                "sent_to_groups": [],
                "failed_groups": [],
            }

        announcement = self.announcements[announcement_id]
        target_groups = groups if groups and len(groups) > 0 else list(self.group_ids)

        if not target_groups:
            return {
                "success": False,
                "error": "No groups available to send announcement",
                "sent_to_groups": [],
                "failed_groups": [],
            }

        sent_to_groups = []
        failed_groups = []

        for group_id in target_groups:
            try:
                if announcement.get("photo_url"):
                    await self.bot.send_photo(
                        chat_id=group_id,
                        photo=announcement["photo_url"],
                        caption=announcement["text"],
                    )
                else:
                    await self.bot.send_message(
                        chat_id=group_id, text=f"📢 {announcement['text']}"
                    )
                sent_to_groups.append(group_id)
            except Exception:
                failed_groups.append({"group_id": group_id, "error": "send_failed"})
                logger.error(
                    "Failed to send announcement to group_id=%s",
                    group_id,
                    exc_info=True,
                )

        return {
            "success": len(sent_to_groups) > 0,
            "sent_to_groups": sent_to_groups,
            "failed_groups": failed_groups,
        }

    async def list_groups(self, limit: int = 10) -> Dict[str, Any]:
        """
        List registered groups.

        Args:
            limit: Maximum number of groups to return

        Returns:
            Dict with list of groups and total count
        """
        groups = [{"group_id": gid} for gid in self.group_ids][:limit]

        return {"groups": groups, "total": len(self.group_ids)}

    async def delete_announcement(self, announcement_id: str) -> Dict[str, Any]:
        """
        Delete a draft announcement.

        Args:
            announcement_id: ID of the announcement to delete

        Returns:
            Dict with deletion status
        """
        if announcement_id not in self.announcements:
            return {
                "success": False,
                "error": f"Announcement {announcement_id} not found",
            }

        del self.announcements[announcement_id]

        return {"success": True}

    def get_tools(self) -> List[Tool]:
        """Return Telegram operations as :class:`~agentconnect.prebuilt.tools.Tool` values."""
        return [
            Tool(
                name="send_telegram_message",
                description=(
                    "Send a text message to a DIFFERENT Telegram chat or group. "
                    "Do not use this to reply to the current user. Return normal "
                    "response text for that."
                ),
                parameters=_tool_parameters(SendMessageInput),
                handler=self.send_message,
            ),
            Tool(
                name="send_telegram_photo",
                description="Send a photo to a Telegram chat. URL, file_id, or local path.",
                parameters=_tool_parameters(SendPhotoInput),
                handler=self.send_photo,
            ),
            Tool(
                name="send_telegram_document",
                description="Send a document to a Telegram chat. URL, file_id, or local path.",
                parameters=_tool_parameters(SendDocumentInput),
                handler=self.send_document,
            ),
            Tool(
                name="download_telegram_file",
                description="Download a Telegram file by file_id and save it locally.",
                parameters=_tool_parameters(DownloadFileInput),
                handler=self.download_file,
            ),
            Tool(
                name="send_telegram_location",
                description="Send a geographical location to a Telegram chat.",
                parameters=_tool_parameters(SendLocationInput),
                handler=self.send_location,
            ),
            Tool(
                name="edit_telegram_message",
                description="Edit the text of an existing Telegram message.",
                parameters=_tool_parameters(EditMessageInput),
                handler=self.edit_message,
            ),
            Tool(
                name="create_telegram_announcement",
                description="Create an announcement draft to publish to groups later.",
                parameters=_tool_parameters(CreateAnnouncementInput),
                handler=self.create_announcement,
            ),
            Tool(
                name="publish_telegram_announcement",
                description="Publish an announcement to Telegram groups.",
                parameters=_tool_parameters(PublishAnnouncementInput),
                handler=self.publish_announcement,
            ),
            Tool(
                name="list_telegram_groups",
                description="List registered Telegram groups that can receive announcements.",
                parameters=_tool_parameters(ListGroupsInput),
                handler=self.list_groups,
            ),
        ]


def _tool_parameters(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for a tool, without Pydantic ``$defs`` or title."""
    schema = model.model_json_schema()
    for key in ("$defs", "definitions", "title"):
        schema.pop(key, None)
    if "type" not in schema:
        schema["type"] = "object"
    return schema
