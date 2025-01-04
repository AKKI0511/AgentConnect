from typing import List, Optional
from src.core.agent import BaseAgent
from src.core.types import AgentType, MessageType, ModelProvider, ModelName
from src.core.message import Message
from src.providers.provider_factory import ProviderFactory


class AIAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str,
        name: str,
        provider_type: ModelProvider,
        model_name: ModelName,
        api_key: str,
        capabilities: List[str] = None,
    ):
        super().__init__(agent_id, AgentType.AI, name)
        self.capabilities = capabilities or []
        self.conversation_history = []
        self.provider = ProviderFactory.create_provider(provider_type, api_key)
        self.model_name = model_name

    def _format_conversation_history(self):
        """Format conversation history for AI context"""
        formatted_history = []
        for msg in self.conversation_history[-5:]:  # Keep last 5 messages for context
            role = "assistant" if msg.sender_id == self.agent_id else "user"
            formatted_history.append({"role": role, "content": msg.content})
        return formatted_history

    async def process_message(self, message: Message) -> Optional[Message]:
        # Check for exit signal
        if message.content == "__EXIT__":
            return None

        self.conversation_history.append(message)

        try:
            messages = [
                {
                    "role": "system",
                    "content": f"You are {self.name}, an AI assistant. Be helpful and concise.",
                },
                *self._format_conversation_history(),
            ]

            response = await self.provider.generate_response(
                messages=messages,
                model=self.model_name,
                temperature=0.7,
                max_tokens=150,
            )

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=response,
                message_type=MessageType.RESPONSE,
            )

        except Exception as e:
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Error: {str(e)}",
                message_type=MessageType.ERROR,
            )
