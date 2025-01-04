from abc import ABC, abstractmethod
import asyncio
from typing import List, Optional

from src.core.message import Message
from src.core.types import AgentType, MessageType


class BaseAgent(ABC):
    def __init__(self, agent_id: str, agent_type: AgentType, name: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.message_queue = asyncio.Queue()
        self.message_history: List[Message] = []
        self.is_running = True
        self.hub = None  # Will be set when registering with hub

    async def send_message(
        self,
        receiver: "BaseAgent",
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> Message:
        message = Message.create(
            sender_id=self.agent_id,
            receiver_id=receiver.agent_id,
            content=content,
            message_type=message_type,
        )
        await receiver.receive_message(message)
        self.message_history.append(message)
        return message

    async def receive_message(self, message: Message):
        await self.message_queue.put(message)
        self.message_history.append(message)

    @abstractmethod
    async def process_message(self, message: Message) -> Optional[Message]:
        pass

    async def run(self):
        """Process messages from the queue continuously"""
        while self.is_running:
            try:
                message = await self.message_queue.get()
                response = await self.process_message(message)
                if response:
                    # Put the response in the message history
                    self.message_history.append(response)
                    # Get receiver from the hub we're registered with
                    if self.hub:
                        receiver = self.hub.get_agent(response.receiver_id)
                        if receiver:
                            await receiver.message_queue.put(response)
                self.message_queue.task_done()
            except Exception as e:
                print(f"Error processing message: {e}")
