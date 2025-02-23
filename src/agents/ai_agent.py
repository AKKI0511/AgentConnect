from asyncio.log import logger
import time
from typing import List, Optional
from langchain_core.messages import HumanMessage
import asyncio

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
from src.utils.interaction_control import (
    InteractionControl,
    TokenConfig,
    InteractionState,
)


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
        max_tokens_per_minute: int = 5500,
        max_tokens_per_hour: int = 100000,
        is_ui_mode: bool = False,
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
        self.is_ui_mode = is_ui_mode
        self.last_processed_message_id = None
        self.provider_type = provider_type
        self.model_name = model_name
        self.personality = personality
        self.processing_lock = asyncio.Lock()

        # Initialize token counter and interaction control
        token_config = TokenConfig(
            max_tokens_per_minute=max_tokens_per_minute,
            max_tokens_per_hour=max_tokens_per_hour,
        )
        self.interaction_control = InteractionControl(token_config=token_config)

        # Create system config
        system_config = SystemPromptConfig(
            name=name,
            capabilities=self.metadata.capabilities,
            personality=personality,
            temperature=0.7,
            max_tokens=4000,
        )

        # Initialize conversation chain
        self.conversation_chain = ChainFactory.create_conversation_chain(
            provider_type=provider_type,
            model_name=model_name,
            api_key=api_key,
            system_config=system_config,
        )

    async def run(self):
        """Process messages from the queue continuously"""
        try:
            while self.is_running:
                try:
                    # Use wait_for to prevent hanging on message_queue.get()
                    message = await asyncio.wait_for(
                        self.message_queue.get(), timeout=5.0
                    )

                    # Skip if we've already processed this message (for UI mode)
                    if (
                        self.is_ui_mode
                        and message.metadata.get("message_id")
                        == self.last_processed_message_id
                    ):
                        self.message_queue.task_done()
                        continue

                    async with self.processing_lock:
                        # First check if we're in cooldown or at token limit
                        state = await self.interaction_control.process_interaction(0)
                        if state == InteractionState.WAIT:
                            cooldown_duration = (
                                self.interaction_control.token_config.get_cooldown_duration()
                            )
                            if cooldown_duration:
                                logger.info(
                                    f"Agent {self.agent_id} in cooldown for {cooldown_duration} seconds"
                                )
                                cooldown_message = Message.create(
                                    sender_id=self.agent_id,
                                    receiver_id=message.sender_id,
                                    content=f"Agent is in cooldown. Please wait {int(cooldown_duration)} seconds.",
                                    sender_identity=self.identity,
                                    message_type=MessageType.COOLDOWN,
                                    metadata={"cooldown_remaining": cooldown_duration},
                                )
                                await self.send_message(
                                    receiver_id=cooldown_message.receiver_id,
                                    content=cooldown_message.content,
                                    message_type=cooldown_message.message_type,
                                    metadata=cooldown_message.metadata,
                                )
                                self.message_queue.task_done()
                                # Sleep for cooldown duration before processing next message
                                await asyncio.sleep(cooldown_duration)
                                continue

                        elif state == InteractionState.STOP:
                            stop_message = Message.create(
                                sender_id=self.agent_id,
                                receiver_id=message.sender_id,
                                content="Maximum interaction turns reached. Ending conversation.",
                                sender_identity=self.identity,
                                message_type=MessageType.STOP,
                                metadata={"reason": "max_turns_reached"},
                            )
                            await self.send_message(
                                receiver_id=stop_message.receiver_id,
                                content=stop_message.content,
                                message_type=stop_message.message_type,
                                metadata=stop_message.metadata,
                            )
                            self.is_running = False
                            self.message_queue.task_done()
                            continue

                        # Process message only if we're not in cooldown or at limit
                        try:
                            response = await asyncio.wait_for(
                                self.process_message(message), timeout=25.0
                            )
                            if response:
                                await self.send_message(
                                    receiver_id=response.receiver_id,
                                    content=response.content,
                                    message_type=response.message_type,
                                    metadata=response.metadata,
                                )

                                # Update last processed message ID for UI mode
                                if self.is_ui_mode:
                                    self.last_processed_message_id = (
                                        message.metadata.get("message_id")
                                    )

                        except asyncio.TimeoutError:
                            logger.error(
                                f"Timeout processing message from {message.sender_id}"
                            )
                            await self.send_message(
                                receiver_id=message.sender_id,
                                content="Processing timeout - the operation took too long",
                                message_type=MessageType.ERROR,
                                metadata={"error": "timeout"},
                            )
                        except Exception as e:
                            logger.error(f"Error processing message: {str(e)}")
                            await self.send_message(
                                receiver_id=message.sender_id,
                                content=f"Error processing message: {str(e)}",
                                message_type=MessageType.ERROR,
                                metadata={"error": str(e)},
                            )
                        finally:
                            self.message_queue.task_done()

                except asyncio.TimeoutError:
                    # This is normal - just continue waiting for new messages
                    continue
                except Exception as e:
                    logger.error(f"Error in message processing loop: {str(e)}")
                    # Ensure we mark the task as done even on error
                    if not self.message_queue.empty():
                        self.message_queue.task_done()
                    continue

        except asyncio.CancelledError:
            logger.info(f"Agent {self.agent_id} task cancelled, cleaning up...")
            raise
        finally:
            # Cleanup when the loop ends
            self.is_running = False

            # Release the processing lock if held
            if self.processing_lock.locked():
                self.processing_lock.release()

            # Clean up any remaining messages
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
                except Exception as e:
                    logger.exception(f"Error cleaning up remaining messages: {str(e)}")

            # End all active conversations
            for agent_id in list(self.active_conversations.keys()):
                self.end_conversation(agent_id)

            # Clean up conversation chain if needed
            if hasattr(self, "conversation_chain"):
                try:
                    if hasattr(self.conversation_chain, "aclose"):
                        await self.conversation_chain.aclose()
                except Exception as e:
                    logger.exception(f"Error closing conversation chain: {str(e)}")

            logger.info(f"AI Agent {self.agent_id} cleanup completed")

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

        # Check if agent can receive the message
        if not await self.can_receive_message(message.sender_id):
            logger.warning(
                f"Agent {self.agent_id} is in cooldown. Deferring message from {message.sender_id}."
            )
            # Send cooldown message back to the sender
            cooldown_duration = (
                self.interaction_control.token_config.get_cooldown_duration()
            )
            if cooldown_duration:
                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content=f"I am in cooldown for {cooldown_duration} seconds. Please try again later.",
                    sender_identity=self.identity,
                    message_type=MessageType.COOLDOWN,
                    metadata={"cooldown_remaining": cooldown_duration},
                )
            return None

        # Check if conversation should end
        conversation_data = self.active_conversations.get(message.sender_id, {})
        if (
            conversation_data.get("message_count", 0)
            >= self.interaction_control.max_turns
        ):
            self.end_conversation(message.sender_id)
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content="Maximum conversation turns reached. Ending conversation.",
                sender_identity=self.identity,
                message_type=MessageType.STOP,
                metadata={"reason": "max_turns_reached"},
            )

        if message.message_type == MessageType.STOP or "__EXIT__" in message.content:
            self.end_conversation(message.sender_id)
            return None

        # Check if the message is a cooldown notification
        if message.message_type == MessageType.COOLDOWN:
            logger.info(
                f"Agent {message.sender_id} is in cooldown. Cooldown duration: {message.metadata['cooldown_remaining']} seconds."
            )
            return None

        # Check if in cooldown
        if not await self.can_send_message(message.sender_id):
            cooldown_remaining = self.cooldown_until - time.time()
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Agent is in cooldown. Please wait {int(cooldown_remaining)} seconds.",
                sender_identity=self.identity,
                message_type=MessageType.COOLDOWN,
                metadata={
                    "cooldown_remaining": cooldown_remaining,
                },
            )

        try:
            # Check interaction state before making LLM call
            state = await self.interaction_control.process_interaction(0)

            # End conversation for both agents
            if state == InteractionState.STOP:
                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content="Maximum interaction turns reached. Ending conversation.",
                    sender_identity=self.identity,
                    message_type=MessageType.STOP,
                    metadata={"reason": "max_turns_reached"},
                )

            # If in cooldown, set cooldown and return cooldown message
            if state == InteractionState.WAIT:
                cooldown_duration = (
                    self.interaction_control.token_config.get_cooldown_duration()
                )
                self.set_cooldown(cooldown_duration or 60)
                cooldown_remaining = self.cooldown_until - time.time()
                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content=f"Agent is in cooldown. Please wait {int(cooldown_remaining)} seconds.",
                    sender_identity=self.identity,
                    message_type=MessageType.COOLDOWN,
                    metadata={
                        "cooldown_remaining": cooldown_remaining,
                    },
                )

            # Use the conversation chain to generate response
            input_dict = {
                "messages": [HumanMessage(content=message.content)],
            }
            response = await self.conversation_chain.ainvoke(
                input_dict, {"configurable": {"thread_id": f"session_{self.agent_id}"}}
            )
            # Get token counts from response metadata
            total_tokens = response["messages"][-1].usage_metadata.get(
                "total_tokens", 0
            )

            # Update token count after response
            state = await self.interaction_control.process_interaction(total_tokens)

            # If token limit reached set agent in cooldown
            if state == InteractionState.WAIT:
                cooldown_duration = (
                    self.interaction_control.token_config.get_cooldown_duration()
                )
                self.set_cooldown(cooldown_duration or 60)

            # Update conversation message count
            if message.sender_id in self.active_conversations:
                self.active_conversations[message.sender_id]["message_count"] += 1

            response_content = response["messages"][-1].content
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=response_content,
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
