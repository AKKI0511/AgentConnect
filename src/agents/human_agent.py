from typing import Optional
import asyncio
import aioconsole
from colorama import Fore, Style

from src.core.agent import BaseAgent
from src.core.types import AgentType, MessageType, InteractionMode, AgentIdentity
from src.core.message import Message


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
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.HUMAN,
            identity=identity,
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
            capabilities=["text_interaction", "command_execution"],
            organization_id=organization_id,
        )
        self.name = name
        self.is_active = True

    async def start_interaction(self, target_agent: BaseAgent) -> None:
        """Start an interactive session with an AI agent"""

        # Verify target agent's identity
        if not await target_agent.verify_identity():
            print(
                f"{Fore.RED}Error: Target agent's identity verification failed{Style.RESET_ALL}"
            )
            return

        while self.is_active:
            try:
                # Get user input
                user_input = await aioconsole.ainput(
                    f"\n{Fore.GREEN}You: {Style.RESET_ALL}"
                )

                # Handle exit command
                if user_input.lower() in ["exit", "quit", "bye"]:
                    self.is_active = False
                    await self.send_message(
                        target_agent.agent_id,
                        "__EXIT__",
                        MessageType.STOP,
                        {"reason": "user_exit"},
                    )
                    break

                # Send message
                await self.send_message(
                    target_agent.agent_id, user_input, MessageType.TEXT
                )

                # Wait for and handle response
                try:
                    response = await asyncio.wait_for(
                        self.message_queue.get(), timeout=60.0
                    )

                    if response:
                        if response.message_type == MessageType.COOLDOWN:
                            print(
                                f"{Fore.YELLOW}⏳ {response.content}{Style.RESET_ALL}"
                            )
                        elif response.message_type == MessageType.ERROR:
                            print(
                                f"{Fore.RED}❌ Error: {response.content}{Style.RESET_ALL}"
                            )
                        elif response.message_type == MessageType.STOP:
                            print(
                                f"{Fore.YELLOW}🛑 Conversation ended by AI agent{Style.RESET_ALL}"
                            )
                            self.is_active = False
                            break
                        else:
                            print(f"\n{Fore.CYAN}{target_agent.name}:{Style.RESET_ALL}")
                            print(f"{response.content}")
                    else:
                        print(f"{Fore.RED}❌ No response received{Style.RESET_ALL}")

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

        # Verify message security
        if not message.verify(self.identity):
            print(
                f"{Fore.RED}⚠️  Warning: Received message with invalid signature{Style.RESET_ALL}"
            )
            return None

        # Display received message
        print(f"\n{Fore.CYAN}{message.sender_id}:{Style.RESET_ALL}")
        print(f"{message.content}")
        return None
