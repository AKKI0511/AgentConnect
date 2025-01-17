from typing import List, Optional
from langchain_core.messages import HumanMessage

from src.core.agent import BaseAgent
from src.core.types import (
    AgentType,
    MessageType,
    ModelProvider,
    ModelName,
    InteractionMode,
    AgentIdentity,
)
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
        identity: AgentIdentity,
        capabilities: List[str] = None,
        personality: str = "helpful and professional",
        organization_id: Optional[str] = None,
        interaction_modes: List[InteractionMode] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.AI,
            identity=identity,
            interaction_modes=interaction_modes
            or [InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
            capabilities=capabilities or [],
            organization_id=organization_id,
        )
        self.name = name

        # Create system config
        system_config = SystemPromptConfig(
            name=name,
            capabilities=self.metadata.capabilities,
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

    async def process_message(self, message: Message) -> Optional[Message]:
        """Process incoming message and generate response"""
        # Verify message signature
        if not message.verify(self.identity):
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content="Message verification failed",
                sender_identity=self.identity,
                message_type=MessageType.ERROR,
            )

        if message.content == "__EXIT__":
            return None

        try:
            # Use the conversation chain to generate response
            input_dict = {
                "messages": [HumanMessage(content=message.content)],
            }
            response = await self.conversation_chain.ainvoke(
                input_dict, {"configurable": {"thread_id": f"session_{self.agent_id}"}}
            )

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=response["messages"][-1].content,
                sender_identity=self.identity,
                message_type=MessageType.RESPONSE,
            )

        except Exception as e:
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Error: {str(e)}",
                sender_identity=self.identity,
                message_type=MessageType.ERROR,
            )
