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
from agentconnect.agent.base import BaseAgent
from agentconnect.core.kinds import CONTROL_COOLDOWN, CONTROL_STOP, MessageKind
from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentIdentity,
    AgentProfile,
    AgentType,
    Capability,
    InteractionMode,
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
        organization: Optional[str] = None,
        response_callbacks: Optional[List[Callable]] = None,
    ):
        """Initialize the human agent.

        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable name for the agent
            identity: Identity information for the agent
            organization: Organization or entity providing the agent
            response_callbacks: Optional list of callbacks to be called when human responds
        """

        # For HumanAgent distinction, the agent_id must start with 'human'
        if not agent_id.startswith("human"):
            raise ValueError(
                "The agent_id for HumanAgent must start with 'human' prefix for distinction."
            )

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

        # Create the agent profile
        profile = AgentProfile(
            agent_id=agent_id,
            agent_type=AgentType.HUMAN,
            name=name,
            organization=organization,
            capabilities=capabilities,
        )

        super().__init__(
            agent_id=agent_id,
            identity=identity,
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
            profile=profile,
        )

        self.name = name
        self.is_active = True
        self.response_callbacks = response_callbacks or []
        self.last_response_data = {}
        logger.debug("Human agent initialized agent_id=%s", self.agent_id)

    async def start_interaction(self, target_agent: BaseAgent) -> None:
        """Start an interactive session with an AI agent"""

        # Verify target agent's identity
        if not await target_agent.verify_identity():
            print(
                f"{Fore.RED}Error: Target agent's identity verification failed{Style.RESET_ALL}"
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

                # Handle exit command
                if user_input.lower() in ["exit", "quit", "bye"]:
                    self.is_active = False
                    logger.debug(
                        "Sending exit agent_id=%s receiver_id=%s",
                        self.agent_id,
                        target_agent.agent_id,
                    )
                    await self.send_message(
                        target_agent.agent_id,
                        "__EXIT__",
                        MessageKind.EVENT,
                        {"reason": "user_exit", "control": CONTROL_STOP},
                    )
                    break

                # Send message
                await self.send_message(
                    target_agent.agent_id, user_input, MessageKind.EVENT
                )

                # Wait for and handle response
                try:
                    response: Optional[Message] = await self.message_queue.get()
                    if response:
                        if response.control == CONTROL_COOLDOWN:
                            print(
                                f"{Fore.YELLOW}⏳ {response.content}{Style.RESET_ALL}"
                            )
                        elif response.kind == MessageKind.ERROR:
                            print(
                                f"{Fore.RED}❌ Error: {response.content}{Style.RESET_ALL}"
                            )
                            print("-" * 40)
                        elif response.control == CONTROL_STOP:
                            print(
                                f"{Fore.YELLOW}🛑 Conversation ended by AI agent{Style.RESET_ALL}"
                            )
                            self.is_active = False
                            break
                        elif (
                            response.metadata
                            and response.metadata.get("status") == "processing"
                        ):
                            # This is a processing status message
                            print(f"{Fore.BLUE}⚙️ {response.content}{Style.RESET_ALL}")
                        else:
                            print("-" * 40)
                            print(
                                f"{Fore.CYAN}{target_agent.profile.name or target_agent.agent_id}:{Style.RESET_ALL}"
                            )
                            print(f"{response.content}")
                            print("-" * 40)
                    else:
                        print(f"{Fore.RED}❌ No response received{Style.RESET_ALL}")

                    # Mark the message as processed
                    self.message_queue.task_done()

                except asyncio.TimeoutError:
                    print(
                        f"{Fore.YELLOW}⚠️  Response timeout - AI is taking too long{Style.RESET_ALL}"
                    )
                    print(
                        f"{Fore.YELLOW}You can continue typing or type 'exit' to end{Style.RESET_ALL}"
                    )

            except asyncio.CancelledError:
                print(f"{Fore.YELLOW}🛑 Interaction cancelled{Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}You can continue typing or type 'exit' to end{Style.RESET_ALL}"
                )

    async def process_message(self, message: Message) -> Optional[Message]:
        """Process incoming messages from other agents"""
        logger.debug(
            "Processing message agent_id=%s sender_id=%s type=%s",
            self.agent_id,
            message.sender_id,
            message.kind.value,
        )

        # Call the superclass method to handle common message processing logic
        response = await super().process_message(message)
        if response:
            return response

        # Verify message security
        if not message.verify(self.identity):
            print(
                f"{Fore.RED}⚠️  Warning: Received message with invalid signature{Style.RESET_ALL}"
            )
            return None

        # Display received message
        print(f"\n{Fore.CYAN}{message.sender_id}:{Style.RESET_ALL}")
        print(f"{message.content}")
        print("-" * 40)

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
            print(
                f"{Fore.YELLOW}Ending conversation with {message.sender_id}{Style.RESET_ALL}"
            )

            # Send an exit message to the AI
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content="__EXIT__",
                sender_identity=self.identity,
                kind=MessageKind.EVENT,
                control=CONTROL_STOP,
                metadata={"reason": "user_exit"},
            )

        # Log the user input
        if user_input.strip():
            # Send response back to the sender
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=user_input,
                sender_identity=self.identity,
                kind=MessageKind.EVENT,
            )
        else:
            # If the user didn't enter any text, log it but don't send a response
            print(f"{Fore.YELLOW}No response sent.{Style.RESET_ALL}")
            return None

    async def send_message(
        self,
        receiver_id: str,
        content: str,
        kind: MessageKind = MessageKind.EVENT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Override send_message to track human responses and notify callbacks"""
        # Call the original method in the parent class
        message = await super().send_message(receiver_id, content, kind, metadata)

        # Store information about this response
        self.last_response_data = {
            "receiver_id": receiver_id,
            "content": content,
            "kind": kind,
            "timestamp": asyncio.get_event_loop().time(),
        }

        # Notify any registered callbacks
        for callback in self.response_callbacks:
            try:
                callback(self.last_response_data)
            except Exception as e:
                logger.error(
                    "Error in response callback agent_id=%s: %s", self.agent_id, e
                )

        return message

    def add_response_callback(self, callback: Callable) -> None:
        """Add a callback to be notified when the human sends a response"""
        if callback not in self.response_callbacks:
            self.response_callbacks.append(callback)

    def remove_response_callback(self, callback: Callable) -> None:
        """Remove a previously registered callback"""
        if callback in self.response_callbacks:
            self.response_callbacks.remove(callback)
