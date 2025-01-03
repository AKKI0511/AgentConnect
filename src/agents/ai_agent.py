from typing import List, Optional

from src.core.agent import BaseAgent
from src.core.types import AgentType, MessageType
from src.core.message import Message

class AIAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str, capabilities: List[str] = None):
        super().__init__(agent_id, AgentType.AI, name)
        self.capabilities = capabilities or []

    async def process_message(self, message: Message) -> Optional[Message]:
        # Basic message processing logic
        # This would be extended with actual AI capabilities
        response_content = f"Processed: {message.content}"
        return Message.create(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            content=response_content,
            message_type=MessageType.RESPONSE
        )