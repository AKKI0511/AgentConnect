from typing import Dict, Optional

from src.core.agent import BaseAgent
from src.core.types import MessageType


class CommunicationHub:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent):
        self.agents[agent.agent_id] = agent
        agent.hub = self  # Set the hub reference in the agent

    def unregister_agent(self, agent_id: str):
        self.agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self.agents.get(agent_id)

    async def broadcast_message(
        self,
        sender: BaseAgent,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ):
        for agent_id, agent in self.agents.items():
            if agent_id != sender.agent_id:
                await sender.send_message(agent, content, message_type)
