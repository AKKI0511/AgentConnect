from typing import Optional
import asyncio
import aioconsole

from src.core.agent import BaseAgent
from src.core.types import AgentType
from src.core.message import Message


class HumanAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, AgentType.HUMAN, name)
        self.is_active = True

    async def start_interaction(self, target_agent: BaseAgent):
        """Interactive console for human input"""
        print(f"\nStarting chat with {target_agent.name}. Type 'exit' to end.")

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
                        await self.send_message(target_agent, "__EXIT__")
                    break

                # Send message to AI agent
                await self.send_message(target_agent, user_input)

                # Wait for and display AI response
                try:
                    response = await asyncio.wait_for(
                        self.message_queue.get(), timeout=5.0
                    )
                    print(f"\n{target_agent.name} ==========>\n{response.content}\n")
                except asyncio.TimeoutError:
                    print("\nNo response received from AI agent (timeout)\n")

            except asyncio.CancelledError:
                break

    async def process_message(self, message: Message) -> Optional[Message]:
        # Display received message
        print(f"\n{message.sender_id}> {message.content}\n")
        return None
