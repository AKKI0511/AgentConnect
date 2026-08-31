"""Telegram bot that is also an ``AIAgent``.

Join a Team like any other Agent, then ``run()`` to poll Telegram. Incoming
Telegram text goes through the same LiteLLM loop as Team work. Telegram
operations are extra tools.

    from agentconnect.prebuilt import TelegramAIAgent
    from agentconnect.team import Team

    agent = TelegramAIAgent(
        name="telegram-bot",
        model="gpt-4o-mini",
        telegram_token="...",
    )
    team = await Team("content-squad").start()
    await agent.join(team)
    await agent.run()
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any, Optional

from aiogram import types
from dotenv import load_dotenv

from agentconnect.core.identity import AgentIdentity
from agentconnect.prebuilt.ai_agent import AIAgent, CompletionOptions
from agentconnect.prebuilt.loop import CompletionFn
from agentconnect.prebuilt.telegram.bot_manager import TelegramBotManager
from agentconnect.prebuilt.telegram.keyboards import (
    GROUP_CHAT_KEYBOARD,
    PRIVATE_CHAT_KEYBOARD,
)
from agentconnect.prebuilt.telegram.message_processor import TelegramMessageProcessor
from agentconnect.prebuilt.telegram._handlers import HandlerRegistry
from agentconnect.prebuilt.telegram._utils.file_utils import ensure_download_directory
from agentconnect.prebuilt.tools import Tool, merge_tools

logger = logging.getLogger(__name__)

_TELEGRAM_HISTORY_CAP = 40


class TelegramAIAgent(AIAgent):
    """``AIAgent`` with a Telegram bot. Team deliveries use ``process_message``.

    agent = TelegramAIAgent(name="telegram-bot", model="gpt-4o-mini")
    await agent.join(team)
    await agent.run()
    """

    HELP_TEXT = (
        "I'm an AgentConnect Telegram bot. Chat normally, mention me in a group, "
        "or send media.\n\n"
        "<b>Commands:</b>\n"
        "/start - Welcome\n"
        "/help - This message\n"
    )

    profile = {
        "summary": "Talks with people on Telegram and with teammates on a Team.",
        "skills": [
            {
                "name": "telegram_messaging",
                "description": "Send and receive Telegram text, media, and group announcements.",
            }
        ],
        "tags": ["telegram"],
    }

    def __init__(
        self,
        name: str,
        *,
        model: str,
        telegram_token: Optional[str] = None,
        instructions: str = "You are a helpful Telegram assistant.",
        tools: Optional[Sequence[Tool]] = None,
        identity: Optional[AgentIdentity] = None,
        profile: Any = None,
        completion: Optional[CompletionOptions] = None,
        api_key: Optional[str] = None,
        complete: Optional[CompletionFn] = None,
        max_tool_rounds: int = 8,
        include_team_tools: bool = True,
        enable_payments: bool = False,
        wallet_data_dir: Any = None,
        groups_file: str = "groups.txt",
        join_token: Optional[str] = None,
        instance_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Create a Telegram-backed Agent. It has not joined a Team or started polling.

        Args:
            name: Agent name, unique within the Team.
            model: LiteLLM model id.
            telegram_token: BotFather token. ``TELEGRAM_BOT_TOKEN`` is used
                when this is omitted.
            groups_file: Path used to remember registered group chat ids.
        """
        token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("telegram_token is required (or set TELEGRAM_BOT_TOKEN)")
        self.telegram_token = token
        self.groups_file = groups_file
        self.downloads_dir = ensure_download_directory(__file__)
        self._telegram_history: dict[int, list[dict[str, Any]]] = {}
        self.telegram_polling_task: Optional[asyncio.Task] = None
        self.bot_manager = TelegramBotManager(
            token=self.telegram_token,
            groups_file=self.groups_file,
            agent_id=agent_id or name,
        )
        self._initialize_telegram_components()
        telegram_tools: list[Tool] = []
        if self.bot_manager.telegram_tools:
            telegram_tools = self.bot_manager.telegram_tools.get_tools()
        super().__init__(
            name=name,
            model=model,
            profile=profile,
            identity=identity,
            instructions=instructions,
            tools=merge_tools(telegram_tools, list(tools or [])),
            max_tool_rounds=max_tool_rounds,
            completion=completion,
            api_key=api_key,
            complete=complete,
            include_team_tools=include_team_tools,
            enable_payments=enable_payments,
            wallet_data_dir=wallet_data_dir,
            agent_id=agent_id,
            instance_id=instance_id,
            join_token=join_token,
        )
        self.message_processor = TelegramMessageProcessor(
            agent_id=self.agent_id,
            identity=self.identity,
            bot_manager=self.bot_manager,
        )

    def _initialize_telegram_components(self) -> None:
        """Create the Bot, dispatcher, and Telegram tools."""
        if not self.bot_manager.initialize_bot():
            logger.error("Failed to initialize Telegram bot name=%s", self.name)
        if not self.bot_manager.initialize_tools():
            logger.error("Failed to initialize Telegram tools name=%s", self.name)
        self.bot_manager.register_shutdown_handler(self._on_shutdown)

    async def start_telegram_bot(self) -> None:
        """Connect to Telegram and register handlers."""
        if not await self.bot_manager.start_polling():
            raise RuntimeError("Failed to start Telegram bot polling")
        handler_registry = HandlerRegistry()
        callback_map = {
            "handle_start": self._handle_start,
            "handle_help": self._handle_help,
            "handle_about": self._handle_about,
            "handle_view_groups": self._handle_view_groups,
            "handle_group_mention": self._handle_group_mention,
            "handle_media_message": self._handle_media_message,
            "handle_message": self._handle_message,
            "get_help_text": lambda: self.HELP_TEXT,
            "get_bot_user": lambda: self.bot_manager.me,
        }
        await handler_registry.register_all(self.bot_manager.dp, callback_map)

    async def stop_telegram_bot(self) -> None:
        """Stop polling and persist registered group ids."""
        await self.bot_manager.stop_polling()

    async def run(self) -> None:
        """Poll Telegram until cancelled. Join a Team first if teammates should reach you."""
        await self.start_telegram_bot()
        logger.info("Telegram agent polling name=%s", self.name)
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        finally:
            await self.stop_telegram_bot()
            logger.info("Telegram agent stopped name=%s", self.name)

    async def _on_shutdown(self) -> None:
        """Hook for bot_manager shutdown. Group ids are saved by the manager."""
        return None

    on_shutdown = _on_shutdown

    async def _answer_telegram(self, payload: Mapping[str, Any]) -> None:
        """Run the model loop for one Telegram payload and send the reply."""
        chat_id = int(payload["chat_id"])
        content = str(payload.get("content") or "")
        history = self._telegram_history.setdefault(chat_id, [])
        reply = await self.complete(
            content,
            history=history,
            include_team_tools=self.include_team_tools,
        )
        history.append({"role": "user", "content": content})
        history.append({"role": "assistant", "content": reply})
        if len(history) > _TELEGRAM_HISTORY_CAP:
            del history[:-_TELEGRAM_HISTORY_CAP]
        await self.bot_manager.send_message(
            chat_id=chat_id,
            text=reply,
            reply_to_message_id=payload.get("reply_to_message_id"),
        )
        thinking_id = self.bot_manager.processing_messages.pop(chat_id, None)
        if thinking_id is not None and self.bot_manager.bot is not None:
            try:
                await self.bot_manager.bot.delete_message(
                    chat_id=chat_id, message_id=thinking_id
                )
            except Exception:
                pass

    async def _handle_start(self, message: types.Message) -> None:
        """Handle /start."""
        if message.chat.type in ["group", "supergroup"]:
            self.bot_manager.group_ids.add(message.chat.id)
            if self.bot_manager.telegram_tools:
                self.bot_manager.telegram_tools.group_ids = self.bot_manager.group_ids
                self.bot_manager.telegram_tools._save_group_ids()
            await message.answer(
                "Bot added. This group can receive announcements.",
                reply_markup=GROUP_CHAT_KEYBOARD,
            )
            return
        first = ""
        if message.from_user is not None:
            first = message.from_user.first_name or ""
        await message.answer(
            f"Hi {first}. Chat normally, or use the buttons below.",
            reply_markup=PRIVATE_CHAT_KEYBOARD,
        )

    async def _handle_help(self, message: types.Message) -> None:
        """Handle /help."""
        keyboard = (
            PRIVATE_CHAT_KEYBOARD
            if message.chat.type == "private"
            else GROUP_CHAT_KEYBOARD
        )
        await message.answer(self.HELP_TEXT, reply_markup=keyboard)

    async def _handle_about(self, message: types.Message) -> None:
        """Handle the about button."""
        keyboard = (
            PRIVATE_CHAT_KEYBOARD
            if message.chat.type == "private"
            else GROUP_CHAT_KEYBOARD
        )
        await message.answer(
            "AgentConnect Telegram bot. Chat, mention me in a group, or send media.",
            reply_markup=keyboard,
        )

    async def _handle_view_groups(self, message: types.Message) -> None:
        """List registered group ids."""
        if not self.bot_manager.group_ids:
            await message.answer("No groups registered yet.")
            return
        group_list = "\n".join(
            f"• Group ID: <code>{gid}</code>" for gid in self.bot_manager.group_ids
        )
        await message.answer(
            f"Registered groups ({len(self.bot_manager.group_ids)}):\n{group_list}"
        )

    async def _handle_group_mention(self, message: types.Message) -> None:
        """Handle an @mention in a group."""
        try:
            payload = await self.message_processor.process_group_mention(message)
            if payload:
                await self._answer_telegram(payload)
        except Exception:
            logger.error("Error processing group mention", exc_info=True)
            await self._clear_thinking(message.chat.id)
            await message.reply(
                "Sorry, I hit an error. Try again.",
                reply_markup=GROUP_CHAT_KEYBOARD,
            )

    async def _handle_media_message(
        self, message: types.Message, media_type: str
    ) -> None:
        """Handle photos, documents, and other media."""
        try:
            payload = await self.message_processor.process_media_message(
                message, media_type
            )
            if payload:
                await self._answer_telegram(payload)
        except Exception:
            logger.error("Error processing media message", exc_info=True)
            await self._clear_thinking(message.chat.id)
            keyboard = (
                PRIVATE_CHAT_KEYBOARD
                if message.chat.type == "private"
                else GROUP_CHAT_KEYBOARD
            )
            await message.answer(
                "Sorry, I hit an error processing that media.",
                reply_markup=keyboard,
            )

    async def _handle_message(self, message: types.Message) -> None:
        """Handle private-chat text."""
        try:
            payload = await self.message_processor.process_text_message(message)
            if payload:
                await self._answer_telegram(payload)
        except Exception:
            logger.error("Error processing text message", exc_info=True)
            await self._clear_thinking(message.chat.id)
            keyboard = (
                PRIVATE_CHAT_KEYBOARD
                if message.chat.type == "private"
                else GROUP_CHAT_KEYBOARD
            )
            await message.answer(
                "Sorry, I hit an error. Try again.",
                reply_markup=keyboard,
            )

    async def _clear_thinking(self, chat_id: int) -> None:
        thinking_id = self.bot_manager.processing_messages.pop(chat_id, None)
        if thinking_id is None or self.bot_manager.bot is None:
            return
        try:
            await self.bot_manager.bot.delete_message(
                chat_id=chat_id, message_id=thinking_id
            )
        except Exception:
            pass


if __name__ == "__main__":
    load_dotenv()

    async def _main() -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        agent = TelegramAIAgent(
            name="telegram-bot",
            model=model,
            telegram_token=token,
        )
        await agent.run()

    asyncio.run(_main())
