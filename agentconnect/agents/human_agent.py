"""
Human agent implementation for the AgentConnect framework.

This module provides a human agent that can interact with AI agents through
a command-line interface.
"""

# Standard library imports
import asyncio
import logging
from typing import Optional, Callable, List, Dict, Any

# Third-party imports
import aioconsole
from colorama import Fore, Style

# Absolute imports from agentconnect package
from agentconnect.core.agent import BaseAgent
from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentIdentity,
    AgentType,
    Capability,
    InteractionMode,
    MessageType,
)

# Set up logging
logger = logging.getLogger(__name__)


class HumanAgent(BaseAgent):
    """
    Human agent implementation for interactive communication with AI agents.

    This agent handles:

    - Real-time text input/output
    - Message verification and security
    - Graceful conversation management
    - Error handling and recovery
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        identity: AgentIdentity,
        organization_id: Optional[str] = None,
        response_callbacks: Optional[List[Callable]] = None,
    ):
        """Initialize the human agent.

        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable name for the agent
            identity: Identity information for the agent
            organization_id: ID of the organization the agent belongs to
            response_callbacks: Optional list of callbacks to be called when human responds
        """
        # Create Capability objects for human capabilities
        capabilities = [
            Capability(
                name="text_interaction",
                description="Ability to send and receive text messages",
                input_schema={"message": "string"},
                output_schema={"response": "string"},
            ),
            Capability(
                name="command_execution",
                description="Ability to execute commands like exit, help, etc.",
                input_schema={"command": "string"},
                output_schema={"result": "string"},
            ),
        ]

        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.HUMAN,
            identity=identity,
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
            capabilities=capabilities,
            organization_id=organization_id,
        )
        self.name = name
        self.is_active = True
        self.response_callbacks = response_callbacks or []
        self.last_response_data = {}
        logger.info(f"Human Agent {self.agent_id} initialized.")

    def _initialize_llm(self):
        """
        Human agents don't use an LLM.
        """
        logger.debug(
            f"Human Agent {self.agent_id}: _initialize_llm called (no LLM needed)."
        )
        return None

    def _initialize_workflow(self):
        """
        Human agents don't use a workflow.
        """
        logger.debug(
            f"Human Agent {self.agent_id}: _initialize_workflow called (no workflow needed)."
        )
        return None

    async def start_interaction(self, target_agent: BaseAgent) -> None:
        """Start an interactive session with an AI agent"""
        logger.info(
            f"Human Agent {self.agent_id} starting interaction with {target_agent.agent_id}."
        )

        # Verify target agent's identity
        if not await target_agent.verify_identity():
            print(
                f"{Fore.RED}Error: Target agent's identity verification failed{Style.RESET_ALL}"
            )
            logger.error(
                f"Human Agent {self.agent_id}: Target agent {target_agent.agent_id} identity verification failed."
            )
            return

        print(
            f"{Fore.GREEN}Human Agent {self.agent_id} starting interaction with {target_agent.agent_id}{Style.RESET_ALL}"
        )
        print(f"{Fore.GREEN}Exit with 'exit', 'quit', or 'bye'{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Loading...{Style.RESET_ALL}")
        while self.is_active:
            try:
                # Get user input
                user_input = await aioconsole.ainput(
                    f"\n{Fore.GREEN}You: {Style.RESET_ALL}"
                )
                logger.debug(
                    f"Human Agent {self.agent_id} received user input: {user_input[:50]}..."
                )

                # Handle exit command
                if user_input.lower() in ["exit", "quit", "bye"]:
                    self.is_active = False
                    logger.info(
                        f"Human Agent {self.agent_id} sending exit message to {target_agent.agent_id}."
                    )
                    await self.send_message(
                        target_agent.agent_id,
                        "__EXIT__",
                        MessageType.STOP,
                        {"reason": "user_exit"},
                    )
                    break

                # Send message
                logger.info(
                    f"Human Agent {self.agent_id} sending message to {target_agent.agent_id}: {user_input[:50]}..."
                )
                await self.send_message(
                    target_agent.agent_id, user_input, MessageType.TEXT
                )

                # Wait for and handle response
                try:
                    response = await self.message_queue.get()
                    logger.debug(
                        f"Human Agent {self.agent_id} received response from {response.sender_id if response else 'nobody'}."
                    )

                    if response:
                        if response.message_type == MessageType.COOLDOWN:
                            print(
                                f"{Fore.YELLOW}⏳ {response.content}{Style.RESET_ALL}"
                            )
                            logger.info(
                                f"Human Agent {self.agent_id} received cooldown message: {response.content[:50]}..."
                            )
                        elif response.message_type == MessageType.ERROR:
                            print(
                                f"{Fore.RED}❌ Error: {response.content}{Style.RESET_ALL}"
                            )
                            print("-" * 40)
                            logger.error(
                                f"Human Agent {self.agent_id} received error message: {response.content[:50]}..."
                            )
                        elif response.message_type == MessageType.STOP:
                            print(
                                f"{Fore.YELLOW}🛑 Conversation ended by AI agent{Style.RESET_ALL}"
                            )
                            logger.info(
                                f"Human Agent {self.agent_id} received stop message."
                            )
                            self.is_active = False
                            break
                        elif (
                            response.metadata
                            and response.metadata.get("status") == "processing"
                        ):
                            # This is a processing status message
                            print(f"{Fore.BLUE}⚙️ {response.content}{Style.RESET_ALL}")
                            logger.info(
                                f"Human Agent {self.agent_id} received processing status message: {response.content[:50]}..."
                            )
                        else:
                            print("-" * 40)
                            print(f"{Fore.CYAN}{target_agent.name}:{Style.RESET_ALL}")
                            print(f"{response.content}")
                            print("-" * 40)
                            logger.info(
                                f"Human Agent {self.agent_id} received and displayed response: {response.content[:50]}..."
                            )
                    else:
                        print(f"{Fore.RED}❌ No response received{Style.RESET_ALL}")
                        logger.warning(
                            f"Human Agent {self.agent_id} received no response."
                        )

                    # Mark the message as processed
                    self.message_queue.task_done()
                    logger.debug(
                        f"Human Agent {self.agent_id} marked message as processed."
                    )

                except asyncio.TimeoutError:
                    print(
                        f"{Fore.YELLOW}⚠️  Response timeout - AI is taking too long{Style.RESET_ALL}"
                    )
                    logger.warning(f"Human Agent {self.agent_id} response timeout.")
                    print(
                        f"{Fore.YELLOW}You can continue typing or type 'exit' to end{Style.RESET_ALL}"
                    )

            except asyncio.CancelledError:
                print(f"{Fore.YELLOW}🛑 Interaction cancelled{Style.RESET_ALL}")
                logger.info(f"Human Agent {self.agent_id} interaction cancelled.")
                break
            except Exception as e:
                print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
                logger.exception(
                    f"Human Agent {self.agent_id} encountered an error: {str(e)}"
                )
                print(
                    f"{Fore.YELLOW}You can continue typing or type 'exit' to end{Style.RESET_ALL}"
                )

    async def process_message(self, message: Message) -> Optional[Message]:
        """Process incoming messages from other agents"""
        logger.info(
            f"Human Agent {self.agent_id} processing message from {message.sender_id}: {message.content[:50]}..."
        )

        # Call the superclass method to handle common message processing logic
        response = await super().process_message(message)
        if response:
            logger.info(
                f"Human Agent {self.agent_id} returning response from super().process_message: {response.content[:50]}..."
            )
            return response

        # Verify message security
        if not message.verify(self.identity):
            print(
                f"{Fore.RED}⚠️  Warning: Received message with invalid signature{Style.RESET_ALL}"
            )
            logger.warning(
                f"Human Agent {self.agent_id} received message with invalid signature from {message.sender_id}."
            )
            return None

        # Display received message
        print(f"\n{Fore.CYAN}{message.sender_id}:{Style.RESET_ALL}")
        print(f"{message.content}")
        print("-" * 40)
        logger.info(
            f"Human Agent {self.agent_id} displayed received message from {message.sender_id}."
        )

        # Prompt for and get user response
        print(
            f"{Fore.YELLOW}Type your response or use these commands:{Style.RESET_ALL}"
        )
        print(
            f"{Fore.YELLOW}- 'exit', 'quit', or 'bye' to end the conversation{Style.RESET_ALL}"
        )
        print(
            f"{Fore.YELLOW}- Press Enter without typing to skip responding{Style.RESET_ALL}"
        )
        user_input = await aioconsole.ainput(f"\n{Fore.GREEN}You: {Style.RESET_ALL}")

        # Check for exit commands
        if user_input.lower().strip() in ["exit", "quit", "bye"]:
            logger.info(
                f"Human Agent {self.agent_id} ending conversation with {message.sender_id}"
            )
            print(
                f"{Fore.YELLOW}Ending conversation with {message.sender_id}{Style.RESET_ALL}"
            )

            # Send an exit message to the AI
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content="__EXIT__",
                sender_identity=self.identity,
                message_type=MessageType.STOP,
                metadata={"reason": "user_exit"},
            )

        # Log the user input
        if user_input.strip():
            logger.info(
                f"Human Agent {self.agent_id} received user input: {user_input[:50]}..."
            )

            # Send response back to the sender
            logger.info(
                f"Human Agent {self.agent_id} sending response to {message.sender_id}: {user_input[:50]}..."
            )
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=user_input,
                sender_identity=self.identity,
                message_type=MessageType.TEXT,
            )
        else:
            # If the user didn't enter any text, log it but don't send a response
            logger.info(
                f"Human Agent {self.agent_id} skipped responding to {message.sender_id}"
            )
            print(f"{Fore.YELLOW}No response sent.{Style.RESET_ALL}")
            return None

    async def send_message(
        self,
        receiver_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Override send_message to track human responses and notify callbacks"""
        # Call the original method in the parent class
        message = await super().send_message(
            receiver_id, content, message_type, metadata
        )

        # Store information about this response
        self.last_response_data = {
            "receiver_id": receiver_id,
            "content": content,
            "message_type": message_type,
            "timestamp": asyncio.get_event_loop().time(),
        }

        # Notify any registered callbacks
        for callback in self.response_callbacks:
            try:
                callback(self.last_response_data)
            except Exception as e:
                logger.error(f"Error in response callback: {str(e)}")

        return message

    def add_response_callback(self, callback: Callable) -> None:
        """Add a callback to be notified when the human sends a response"""
        if callback not in self.response_callbacks:
            self.response_callbacks.append(callback)
            logger.debug(f"Human Agent {self.agent_id}: Added response callback")

    def remove_response_callback(self, callback: Callable) -> None:
        """Remove a previously registered callback"""
        if callback in self.response_callbacks:
            self.response_callbacks.remove(callback)
            logger.debug(f"Human Agent {self.agent_id}: Removed response callback")
