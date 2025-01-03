from typing import Optional

from src.core.agent import BaseAgent
from src.core.types import AgentType
from src.core.message import Message


class HumanAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, AgentType.HUMAN, name)

    async def process_message(self, message: Message) -> Optional[Message]:
        # In a real implementation, this would interface with the human
        # through some UI/CLI
        print(f"Message received: {message.content}")
        return None
