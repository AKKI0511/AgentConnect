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
