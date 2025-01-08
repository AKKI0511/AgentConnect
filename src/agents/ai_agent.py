from typing import List, Optional
from langchain_core.messages import HumanMessage

from src.core.agent import BaseAgent
from src.core.types import AgentType, MessageType, ModelProvider, ModelName
from src.core.message import Message
from src.prompts.chain_factory import ChainFactory
from src.prompts.templates.system_prompts import SystemPromptConfig


class AIAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str,
        name: str,
        provider_type: ModelProvider,
        model_name: ModelName,
        api_key: str,
        capabilities: List[str] = None,
        personality: str = "helpful and professional",
    ):
        super().__init__(agent_id, AgentType.AI, name)
        self.capabilities = capabilities or []

        # Create system config
        system_config = SystemPromptConfig(
            name=name,
            capabilities=self.capabilities,
            personality=personality,
            temperature=0.7,
            max_tokens=150,
        )

        # Initialize conversation chain
        self.conversation_chain = ChainFactory.create_conversation_chain(
            provider_type=provider_type,
            model_name=model_name,
            api_key=api_key,
            system_config=system_config,
        )
        self.session_id = f"session_{agent_id}"
        self.config = {"configurable": {"thread_id": self.session_id}}

    async def process_message(self, message: Message) -> Optional[Message]:
        if message.content == "__EXIT__":
            return None

        try:
            # Use the conversation chain to generate response
            input_dict = {
                "messages": [HumanMessage(message.content)],
            }
            response = await self.conversation_chain.ainvoke(input_dict, self.config)

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=response["messages"][-1],
                message_type=MessageType.RESPONSE,
            )

        except Exception as e:
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Error: {str(e)}",
                message_type=MessageType.ERROR,
            )
