"""
AgentConnect Telegram AI Agent implementation.

This module provides a Telegram bot interface for AgentConnect, allowing users to
interact with an AI agent through Telegram.
"""

import asyncio
import logging
import os
from typing import Optional, List

from dotenv import load_dotenv
from aiogram import types
from langchain.tools import BaseTool
from langchain_core.callbacks import BaseCallbackHandler

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.telegram.bot_manager import TelegramBotManager
from agentconnect.agents.telegram.message_processor import TelegramMessageProcessor
from agentconnect.agents.telegram.keyboards import (
    PRIVATE_CHAT_KEYBOARD,
    GROUP_CHAT_KEYBOARD,
)
from agentconnect.agents.telegram._handlers import HandlerRegistry
from agentconnect.agents.telegram._utils.file_utils import ensure_download_directory
from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentIdentity,
    InteractionMode,
    Capability,
    MessageType,
    ModelName,
    ModelProvider,
)
from agentconnect.communication.hub import CommunicationHub
from agentconnect.core.registry import AgentRegistry

logger = logging.getLogger(__name__)


class TelegramAIAgent(AIAgent):
    """
    An AgentConnect agent that interacts with users through Telegram.

    This agent extends AIAgent to provide Telegram integration, enabling:

    - Natural language conversations with users via Telegram private chats
    - Group chat interactions through bot mentions
    - Media message handling (photos, documents, voice, etc.)
    - Announcements to registered groups
    - Integration with other AgentConnect agents via collaboration requests

    The agent connects to the Telegram API and processes messages concurrently with
    AgentConnect inter-agent communications, allowing it to serve as both a user interface
    and a collaborative agent within the AgentConnect ecosystem.

    Args:
        agent_id (str): Unique identifier for the agent
        name (str): Human-readable name for the agent (appears in Telegram)
        provider_type (ModelProvider): Type of LLM provider (e.g., GOOGLE, OPENAI)
        model_name (ModelName): Specific LLM to use (e.g., GEMINI2_FLASH, GPT4)
        api_key (str): API key for the LLM provider
        identity (AgentIdentity): Identity information for the agent
        capabilities (List[Capability], optional): Additional capabilities beyond Telegram-specific ones
        personality (str, optional): Description of the agent's personality
        organization_id (str, optional): ID of the organization the agent belongs to
        interaction_modes (List[InteractionMode], optional): Supported interaction modes
        groups_file (str, optional): File path to store registered group IDs
        max_tokens_per_minute (int, optional): Rate limiting for token usage per minute
        max_tokens_per_hour (int, optional): Rate limiting for token usage per hour
        telegram_token (str, optional): Telegram Bot API token (can also use TELEGRAM_BOT_TOKEN env var)

    Note:
        When running the agent, both the Telegram bot polling and AgentConnect message
        processing loops run concurrently, allowing the agent to respond to both
        Telegram users and other agents in the AgentConnect ecosystem.

    Example:
        .. code-block:: python

            from agentconnect.agents.telegram import TelegramAIAgent
            from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName

            # Initialize the agent
            agent = TelegramAIAgent(
                agent_id="telegram_bot",
                name="My Assistant",
                provider_type=ModelProvider.GOOGLE,
                model_name=ModelName.GEMINI2_FLASH,
                api_key="your_google_api_key",
                identity=AgentIdentity.create_key_based(),
                telegram_token="your_telegram_token"
            )

            # Register with communication hub
            await hub.register_agent(agent)

            # Start the agent
            await agent.run()
    """

    # Common message texts
    HELP_TEXT = (
        "I'm an AgentConnect-powered conversational Telegram bot. Here's what I can do:\n\n"
        "• Chat with you about any topic (just type normally)\n"
        "• Create and send announcements to groups\n"
        "• Process your messages using AI capabilities\n"
        "• Collaborate with other agents when needed\n\n"
        "<b>Commands:</b>\n"
        "/start - Restart the bot or get welcome message\n"
        "/help - Show this help message\n"
        "\nYou can also use the buttons below to access specific features."
    )

    def __init__(
        self,
        agent_id: str,
        name: str,
        provider_type: ModelProvider,
        model_name: ModelName,
        api_key: str,
        identity: AgentIdentity,
        capabilities: List[Capability] = None,
        personality: str = "helpful and friendly",
        organization_id: Optional[str] = None,
        interaction_modes: List[InteractionMode] = [
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
        groups_file: str = "groups.txt",
        max_tokens_per_minute: int = 5500,
        max_tokens_per_hour: int = 100000,
        telegram_token: Optional[str] = None,
        enable_payments: bool = False,
        verbose: bool = False,
        wallet_data_dir: Optional[str] = None,
        external_callbacks: Optional[List[BaseCallbackHandler]] = None,
    ):
        """
        Initialize a Telegram AI Agent.

        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable name for the agent (appears in Telegram)
            provider_type: Type of LLM provider (e.g., GOOGLE, OPENAI)
            model_name: Specific LLM to use (e.g., GEMINI2_FLASH, GPT4)
            api_key: API key for the LLM provider
            identity: Identity information for the agent
            capabilities: Additional capabilities beyond Telegram-specific ones
            personality: Description of the agent's personality
            organization_id: ID of the organization the agent belongs to
            interaction_modes: Supported interaction modes
            groups_file: File path to store registered group IDs
            max_tokens_per_minute: Rate limiting for token usage per minute
            max_tokens_per_hour: Rate limiting for token usage per hour
            telegram_token: Telegram Bot API token (can also use TELEGRAM_BOT_TOKEN env var)
            enable_payments: Whether to enable payments
            verbose: Whether to enable verbose logging
            wallet_data_dir: Directory to store wallet data
            external_callbacks: List of external callbacks to use
        """
        # Define Telegram-specific capabilities
        telegram_capabilities = [
            Capability(
                name="telegram_messaging",
                description="Ability to send and receive messages through Telegram, including text, photos, documents, voice messages, and locations",
                input_schema={
                    "message": "string",
                    "chat_id": "int",
                    "media_type": "string",
                    "reply_to_message_id": "int",
                },
                output_schema={"success": "boolean", "message_id": "int"},
            ),
            Capability(
                name="file_handling",
                description="Ability to download and process files sent by Telegram users",
                input_schema={"file_id": "string", "file_type": "string"},
                output_schema={
                    "success": "boolean",
                    "file_path": "string",
                    "file_size": "int",
                },
            ),
            Capability(
                name="announcement_management",
                description="Ability to create and publish announcements to Telegram groups",
                input_schema={
                    "text": "string",
                    "photo_url": "string",
                    "groups": "list",
                },
                output_schema={"success": "boolean", "sent_to_groups": "list"},
            ),
            Capability(
                name="group_management",
                description="Ability to track and manage Telegram groups",
                input_schema={"action": "string", "group_id": "int"},
                output_schema={"success": "boolean", "groups": "list"},
            ),
            Capability(
                name="location_handling",
                description="Ability to receive and send location data through Telegram",
                input_schema={
                    "latitude": "float",
                    "longitude": "float",
                    "chat_id": "int",
                },
                output_schema={"success": "boolean", "message_id": "int"},
            ),
        ]

        # Combine provided capabilities with Telegram-specific ones
        all_capabilities = (capabilities or []) + telegram_capabilities

        # Initialize Telegram-specific components
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.groups_file = groups_file

        # Initialize the downloads directory
        self.downloads_dir = ensure_download_directory(__file__)

        # Create the bot manager
        self.bot_manager = TelegramBotManager(
            token=self.telegram_token,
            groups_file=self.groups_file,
        )

        # Initialize the bot and tools
        self._initialize_telegram_components()

        # Initialize the message processor
        self.message_processor = TelegramMessageProcessor(
            agent_id=agent_id,
            identity=identity,
            bot_manager=self.bot_manager,
        )

        # Initialize processed message tracking
        self._processed_message_ids = set()

        # Initialize the telegram polling task
        self.telegram_polling_task = None

        # Initialize the AIAgent with all capabilities and custom tools
        super().__init__(
            agent_id=agent_id,
            name=name,
            provider_type=provider_type,
            model_name=model_name,
            api_key=api_key,
            identity=identity,
            capabilities=all_capabilities,
            personality=personality,
            organization_id=organization_id,
            interaction_modes=interaction_modes,
            max_tokens_per_minute=max_tokens_per_minute,
            max_tokens_per_hour=max_tokens_per_hour,
            custom_tools=self._get_custom_tools(),  # Pass the custom tools to AIAgent
            enable_payments=enable_payments,
            verbose=verbose,
            wallet_data_dir=wallet_data_dir,
            external_callbacks=external_callbacks,
        )

    def _initialize_telegram_components(self):
        """Initialize Telegram bot and tools."""
        # Initialize the bot
        if not self.bot_manager.initialize_bot():
            logger.error("Failed to initialize Telegram bot")

        # Initialize the tools
        if not self.bot_manager.initialize_tools():
            logger.error("Failed to initialize Telegram tools")

        # Register the shutdown handler
        self.bot_manager.register_shutdown_handler(self._on_shutdown)

    def _get_custom_tools(self) -> List[BaseTool]:
        """
        Get custom tools for the agent workflow.

        Returns:
            List of BaseTool instances
        """
        if self.bot_manager and self.bot_manager.telegram_tools:
            return self.bot_manager.telegram_tools.get_langchain_tools()
        return []

    # The get_custom_tools method should be renamed to be private
    # and aliased in __init__ to preserve the existing public API
    get_custom_tools = _get_custom_tools

    async def start_telegram_bot(self):
        """
        Start the Telegram bot polling.

        This method initializes the bot's connection to the Telegram API and
        registers all message handlers.

        Returns:
            None

        Raises:
            RuntimeError: If the Telegram bot cannot be started
        """
        if not await self.bot_manager.start_polling():
            logger.error("Failed to start Telegram bot polling")
            return

        # Register all handlers
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
        logger.info("All handlers registered")

    async def stop_telegram_bot(self):
        """
        Stop the Telegram bot polling.

        This method gracefully shuts down the Telegram bot, closing the connection
        to the Telegram API and saving any persistent data like registered group IDs.
        It should be called before shutting down the application to ensure clean termination.

        Returns:
            None
        """
        await self.bot_manager.stop_polling()

    # The internal _keep_alive method is kept for implementation purposes
    # but is not part of the public API

    async def process_message(self, message: Message) -> Message | None:
        """
        Process an incoming AgentConnect message.

        This overrides the AIAgent.process_message method to handle
        Telegram-specific message processing, including both direct Telegram messages
        and collaboration requests from other agents.
        """
        # Check if this is a Telegram message (sent from ourselves to ourselves with Telegram metadata)
        if (
            message.sender_id == self.agent_id
            and message.receiver_id == self.agent_id
            and message.metadata
            and message.metadata.get("is_telegram_message")
        ):
            try:
                # Process the message through the agent workflow
                response = await self.message_processor.process_agent_response(
                    workflow=self.workflow,
                    message=message,
                    interaction_control=self.interaction_control,
                )

                if response:
                    # Send the response back to Telegram
                    await self.bot_manager.send_message(
                        chat_id=response["chat_id"],
                        text=response["content"],
                        reply_to_message_id=response["reply_to_message_id"],
                    )
                else:
                    logger.error("Error processing message: empty response")

                # Don't return anything since we've handled the response
                return None
            except Exception as e:
                logger.exception(f"Error in Telegram message processing: {e}")

                # Try to send an error message to the user
                try:
                    telegram_chat_id = int(message.metadata.get("telegram_chat_id"))
                    await self.bot_manager.send_message(
                        chat_id=telegram_chat_id,
                        text="I'm sorry, I encountered an error while processing your message. Please try again.",
                    )
                except Exception as e:
                    logger.exception(f"Error sending error message to user: {e}")
                    pass

                # Don't pass to parent class for Telegram messages
                return None

        # For non-Telegram messages, let the parent class handle it
        response = await super().process_message(message)

        # If we got a response from the parent method, we need to handle it
        if response:
            # Only send back to Telegram if it's a regular response message
            if (
                response.message_type == MessageType.RESPONSE
                and message.metadata
                and message.metadata.get("is_telegram_message")
            ):
                try:
                    # Extract the chat ID from the metadata
                    telegram_chat_id = int(message.metadata.get("telegram_chat_id"))

                    # Check if we should reply to a message ID
                    reply_to_message_id = message.metadata.get("reply_to_message_id")

                    # Send the response to Telegram
                    await self.bot_manager.send_message(
                        chat_id=telegram_chat_id,
                        text=response.content,
                        reply_to_message_id=reply_to_message_id,
                    )

                    # Return None because we've handled the response ourselves
                    return None
                except ValueError:
                    logger.error(
                        f"Invalid telegram_chat_id format: {message.metadata.get('telegram_chat_id')}"
                    )

            # Return the original response for non-Telegram-related responses
            return response

        return None

    async def run(self):
        """
        Start the Telegram bot and the agent's message processing loop.

        This method starts two concurrent processes:
        1. The Telegram bot polling loop that listens for messages from Telegram users
        2. The parent AIAgent's message processing loop that handles inter-agent communications

        Both processes run concurrently, allowing the agent to serve as both a Telegram bot
        and an AgentConnect collaborative agent simultaneously.

        Returns:
            None

        Raises:
            RuntimeError: If the Telegram bot cannot be started
            ConnectionError: If there are network issues with the Telegram API
            Exception: Any unhandled exceptions from either processing loop
        """
        # Mark agent as running
        self.is_running = True
        logger.info(f"Starting Telegram agent {self.agent_id}")

        try:
            # Start the Telegram bot
            await self.start_telegram_bot()

            # Start the BaseAgent's message processing loop by calling the parent class run method
            # This will process messages from other agents through the AgentConnect message queue
            agent_processing_task = asyncio.create_task(super().run())

            # Wait for either task to complete (or be cancelled)
            done, pending = await asyncio.wait(
                [agent_processing_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel any pending tasks
            for task in pending:
                task.cancel()

            # Wait for the cancelled tasks to finish
            await asyncio.gather(*pending, return_exceptions=True)

        except asyncio.CancelledError:
            logger.info(f"Agent {self.agent_id} run task was cancelled")
        except Exception as e:
            logger.exception(f"Error in Telegram agent run: {str(e)}")
        finally:
            # Clean up
            self.is_running = False
            await self.stop_telegram_bot()
            logger.info(f"Telegram agent {self.agent_id} stopped")

    async def _on_shutdown(self):
        """
        Handler for bot shutdown.
        """
        # This is called when the bot is shutting down
        # There's no need to handle group IDs saving here as the bot_manager
        # will handle it in stop_polling

    # Rename the old method to be private, and then alias it to keep backward compatibility
    on_shutdown = _on_shutdown

    # Handler methods should all be internal implementation details
    async def _handle_start(self, message: types.Message):
        """
        Handle the /start command.
        """
        if message.chat.type in ["group", "supergroup"]:
            # Add group to registered list
            self.bot_manager.group_ids.add(message.chat.id)
            if self.bot_manager.telegram_tools:
                self.bot_manager.telegram_tools.group_ids = self.bot_manager.group_ids
                self.bot_manager.telegram_tools._save_group_ids()

            await message.answer(
                "✅ Bot added! This group will receive announcements.",
                reply_markup=GROUP_CHAT_KEYBOARD,
            )
            logger.info(f"📌 Group added: {message.chat.title} ({message.chat.id})")
        else:
            # Send welcome message in private chat
            await message.answer(
                f"👋 Hi {message.from_user.first_name}! I'm an AgentConnect-powered Telegram bot. I can:\n\n"
                "• Have normal conversations with you just like ChatGPT\n"
                "• Create and send announcements to groups\n"
                "• Collaborate with other agents when needed\n\n"
                "Just start talking to me or use the buttons below!",
                reply_markup=PRIVATE_CHAT_KEYBOARD,
            )

            # Also process through AgentConnect after a small delay
            await asyncio.sleep(0.5)
            await message.answer(
                "You don't need to use any special commands - just chat with me naturally!"
            )

    async def _handle_help(self, message: types.Message):
        """
        Handle the /help command.
        """
        # Choose the appropriate keyboard based on chat type
        keyboard = (
            PRIVATE_CHAT_KEYBOARD
            if message.chat.type == "private"
            else GROUP_CHAT_KEYBOARD
        )
        await message.answer(self.HELP_TEXT, reply_markup=keyboard)

    async def _handle_about(self, message: types.Message):
        """
        Handle the About button.
        """
        about_text = (
            "🤖 <b>AgentConnect Telegram Bot</b>\n\n"
            "I'm powered by the AgentConnect framework, which enables me to process your messages "
            "using AI capabilities and collaborate with other specialized agents when needed.\n\n"
            "I can help with creating and sending announcements to Telegram groups, "
            "answering questions, and having natural conversations with you.\n\n"
            "For more information about the AgentConnect framework, visit: "
            "https://github.com/AKKI0511/AgentConnect"
        )
        # Choose the appropriate keyboard based on chat type
        keyboard = (
            PRIVATE_CHAT_KEYBOARD
            if message.chat.type == "private"
            else GROUP_CHAT_KEYBOARD
        )
        await message.answer(about_text, reply_markup=keyboard)

    async def _handle_view_groups(self, message: types.Message):
        """
        Handle the View Groups button.
        """
        if not self.bot_manager.group_ids:
            await message.answer("⚠ No groups registered yet.")
        else:
            group_list = "\n".join(
                [
                    f"• Group ID: <code>{gid}</code>"
                    for gid in self.bot_manager.group_ids
                ]
            )
            await message.answer(
                f"✅ Registered Groups ({len(self.bot_manager.group_ids)}):\n{group_list}"
            )

    async def _handle_group_mention(self, message: types.Message):
        """
        Handle mentions in group chats.
        """
        try:
            # Process the message through the message processor
            agent_message = await self.message_processor.process_group_mention(message)

            # Process the message through AgentConnect
            if agent_message:
                await self.receive_message(agent_message)
        except Exception as e:
            logger.error(f"Error processing group mention: {str(e)}")
            # Delete thinking message
            try:
                if message.chat.id in self.bot_manager.processing_messages:
                    await self.bot_manager.bot.delete_message(
                        chat_id=message.chat.id,
                        message_id=self.bot_manager.processing_messages[
                            message.chat.id
                        ],
                    )
                    del self.bot_manager.processing_messages[message.chat.id]
            except Exception:
                pass

            # For error messages, include the group chat keyboard
            await message.reply(
                "❌ Sorry, I encountered an error while processing your message. Please try again later.",
                reply_markup=GROUP_CHAT_KEYBOARD,
            )

    async def _handle_media_message(self, message: types.Message, media_type: str):
        """
        Handle media messages.
        """
        try:
            # Process the message through the message processor
            agent_message = await self.message_processor.process_media_message(
                message, media_type
            )

            # Process the message through AgentConnect
            if agent_message:
                await self.receive_message(agent_message)
        except Exception as e:
            logger.error(f"Error processing media message: {str(e)}")
            # Delete thinking message
            try:
                if message.chat.id in self.bot_manager.processing_messages:
                    await self.bot_manager.bot.delete_message(
                        chat_id=message.chat.id,
                        message_id=self.bot_manager.processing_messages[
                            message.chat.id
                        ],
                    )
                    del self.bot_manager.processing_messages[message.chat.id]
            except Exception:
                pass

            # For error messages, include the appropriate keyboard
            keyboard = (
                PRIVATE_CHAT_KEYBOARD
                if message.chat.type == "private"
                else GROUP_CHAT_KEYBOARD
            )
            await message.answer(
                "❌ Sorry, I encountered an error while processing your media. Please try again later.",
                reply_markup=keyboard,
            )

    async def _handle_message(self, message: types.Message):
        """
        Handle text messages.
        """
        try:
            # Process the message through the message processor
            agent_message = await self.message_processor.process_text_message(message)

            # Process the message through AgentConnect
            if agent_message:
                await self.receive_message(agent_message)
        except Exception as e:
            logger.error(f"Error processing text message: {str(e)}")
            # Delete thinking message
            try:
                if message.chat.id in self.bot_manager.processing_messages:
                    await self.bot_manager.bot.delete_message(
                        chat_id=message.chat.id,
                        message_id=self.bot_manager.processing_messages[
                            message.chat.id
                        ],
                    )
                    del self.bot_manager.processing_messages[message.chat.id]
            except Exception:
                pass

            # For error messages, include the appropriate keyboard
            keyboard = (
                PRIVATE_CHAT_KEYBOARD
                if message.chat.type == "private"
                else GROUP_CHAT_KEYBOARD
            )
            await message.answer(
                "❌ Sorry, I encountered an error while processing your message. Please try again later.",
                reply_markup=keyboard,
            )


if __name__ == "__main__":
    # Configure logging
    from agentconnect.utils.logging_config import setup_logging, LogLevel

    setup_logging(level=LogLevel.INFO)

    # Variables to track what needs to be cleaned up
    agent = None
    hub = None

    try:
        # Load environment variables
        load_dotenv()

        # Get API keys
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        openai_api_key = os.getenv("GOOGLE_API_KEY")

        if not telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

        if not openai_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set!")

        # Create async function to run everything
        async def main():
            # Use global instead of nonlocal since we're at module level
            global agent, hub
            try:
                # Create agent registry and communication hub
                # These need to be created inside the async function
                registry = AgentRegistry()
                hub = CommunicationHub(registry)

                # Create agent
                agent = TelegramAIAgent(
                    agent_id="telegram_ai_agent",
                    name="AgentConnect Telegram Bot",
                    provider_type=ModelProvider.GOOGLE,
                    model_name=ModelName.GEMINI2_FLASH,
                    api_key=openai_api_key,
                    identity=AgentIdentity.create_key_based(),
                    personality="helpful, friendly, and conversational",
                    telegram_token=telegram_token,
                )

                # Register agent with hub
                if not await hub.register_agent(agent):
                    logger.error("Failed to register agent with hub")
                    return

                logger.info(f"Successfully registered agent {agent.agent_id} with hub")

                # Run the agent directly - DON'T create a task that will exit immediately
                await agent.run()

            except asyncio.CancelledError:
                logger.info("Main task was cancelled")
            except Exception as e:
                logger.exception(f"Error in main function: {e}")
            finally:
                # We don't handle final cleanup here - it will be done in the outer try/finally
                pass

        # Create a main task we can cancel on keyboard interrupt
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Telegram AI Agent stopped by keyboard interrupt.")
    except Exception as e:
        logger.error(f"Error running Telegram AI Agent: {e}")
    finally:
        # Clean up resources
        async def cleanup():
            try:
                # Cleanup the agent if it exists
                if agent and hasattr(agent, "stop_telegram_bot"):
                    logger.info("Stopping Telegram bot...")
                    await agent.stop_telegram_bot()

                # Unregister from hub if registered
                if agent and hub and hasattr(agent, "hub") and agent.hub:
                    logger.info(f"Unregistering agent {agent.agent_id} from hub...")
                    await hub.unregister_agent(agent.agent_id)
                    logger.info(f"Unregistered agent {agent.agent_id} from hub")

            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        # Run the cleanup
        try:
            asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")

        logger.info("Telegram AI Agent shutdown complete.")
