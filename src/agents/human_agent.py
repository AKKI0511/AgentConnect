from typing import Optional
import asyncio
import aioconsole

from src.core.agent import BaseAgent
from src.core.types import AgentType, MessageType, InteractionMode, AgentIdentity
from src.core.message import Message


class HumanAgent(BaseAgent):
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

    async def start_interaction(self, target_agent: BaseAgent):
        """Interactive console for human input"""
        print(f"\nStarting chat with {target_agent.name}. Type 'exit' to end.")

        # Verify target agent's identity before starting
        if not await target_agent.verify_identity():
            print("Error: Target agent's identity could not be verified")
            return

        while self.is_active:
            try:
                # Get human input
                user_input = await aioconsole.ainput(f"{self.name}> ")

                if user_input.lower() == "exit":
                    self.is_active = False
                    # Signal the AI agent to stop
                    if isinstance(target_agent, BaseAgent):
                        target_agent.is_running = False
                        # Send one last message to unblock the AI's message queue
                        await self.send_message(
                            target_agent.agent_id, "__EXIT__", MessageType.COMMAND
                        )
                    break

                # Send human input to target agent
                await self.send_message(
                    target_agent.agent_id, user_input, MessageType.TEXT
                )

                # Wait for and display AI response
                try:
                    response = await asyncio.wait_for(
                        self.message_queue.get(), timeout=5.0
                    )
                    if response.verify(target_agent.identity):
                        print(f"\n{target_agent.name}==========>\n{response.content}\n")
                    else:
                        print("\nWarning: Received message with invalid signature\n")
                except asyncio.TimeoutError:
                    print("\nNo response received from AI agent (timeout)\n")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"\nError during interaction: {e}\n")

    async def process_message(self, message: Message) -> Optional[Message]:
        """Process incoming message"""
        # Verify message signature
        if not message.verify(self.identity):
            print("\nWarning: Received message with invalid signature\n")
            return None

        # Display received message
        print(f"\n{message.sender_id}> {message.content}\n")
        return None
