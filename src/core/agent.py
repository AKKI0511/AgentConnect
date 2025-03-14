from abc import ABC, abstractmethod
import asyncio
from typing import List, Optional, Dict, TYPE_CHECKING
import time
import logging

from src.core.message import Message
from src.core.types import (
    AgentType,
    MessageType,
    InteractionMode,
    AgentMetadata,
    AgentIdentity,
    SecurityError,
    VerificationStatus,
)

if TYPE_CHECKING:
    from src.communication.hub import CommunicationHub
    from src.core.registry import AgentRegistry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        identity: AgentIdentity,
        interaction_modes: List[InteractionMode],
        capabilities: List[str] = None,
        organization_id: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.identity = identity
        self.metadata = AgentMetadata(
            agent_id=agent_id,
            agent_type=agent_type,
            identity=identity,
            organization_id=organization_id,
            capabilities=capabilities or [],
            interaction_modes=interaction_modes,
        )
        self.message_queue = asyncio.Queue()
        self.message_history: List[Message] = []
        self.is_running = True
        self.registry: Optional["AgentRegistry"] = None
        self.hub: Optional["CommunicationHub"] = None
        self.active_conversations = {}
        self.cooldown_until = 0

    async def _verify_ethereum_did(self) -> bool:
        """Verify Ethereum-based DID"""
        try:
            # Here you would typically:
            # 1. Resolve the DID document from Ethereum
            # 2. Verify the public key matches the DID
            # 3. Verify the key can sign/verify messages

            # For MVP, we'll do basic format verification
            # TODO: Implement full Ethereum DID verification
            return True
        except Exception:
            return False

    async def _verify_key_did(self) -> bool:
        """Verify key-based DID"""
        try:
            # Here you would typically:
            # 1. Decode the multibase-encoded public key
            # 2. Verify it matches the stored public key
            # 3. Verify the key can sign/verify messages

            # For MVP, we'll do basic format verification
            # TODO: Implement full key-based DID verification
            return True
        except Exception:
            return False

    async def verify_identity(self) -> bool:
        """Verify agent's DID and update verification status"""
        try:
            # Verify DID using did:ethr or did:key
            if self.identity.did.startswith("did:ethr:"):
                verified = await self._verify_ethereum_did()
            elif self.identity.did.startswith("did:key:"):
                verified = await self._verify_key_did()
            else:
                raise ValueError(f"Unsupported DID method: {self.identity.did}")

            self.identity.verification_status = (
                VerificationStatus.VERIFIED if verified else VerificationStatus.FAILED
            )
            return verified
        except Exception as e:
            self.identity.verification_status = VerificationStatus.FAILED
            raise SecurityError(f"Identity verification failed: {e}")

    async def send_message(
        self,
        receiver_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
    ) -> Message:
        """Create and send a message through the hub"""
        if not self.hub:
            raise RuntimeError("Agent not registered with hub")

        # Create the message
        message = Message.create(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            content=content,
            sender_identity=self.identity,
            message_type=message_type,
            metadata=metadata,
        )

        # Send through hub instead of directly to receiver
        if not await self.hub.route_message(message):
            raise ValueError("Failed to route message")

        self.message_history.append(message)
        return message

    async def receive_message(self, message: Message):
        """Receive and queue a message"""
        await self.message_queue.put(message)
        self.message_history.append(message)

    @abstractmethod
    async def process_message(self, message: Message) -> Optional[Message]:
        """Process incoming message - must be implemented by subclasses"""
        pass

    async def run(self):
        """Process messages from the queue continuously"""
        try:
            while self.is_running:
                try:
                    # Use wait_for to prevent hanging on message_queue.get()
                    message = await asyncio.wait_for(
                        self.message_queue.get(), timeout=5.0
                    )

                    if message.message_type == MessageType.COOLDOWN:
                        logger.info(
                            f"Received cooldown message from {message.sender_id}. Cooldown duration: {message.metadata['cooldown_remaining']} seconds."
                        )
                        self.message_queue.task_done()
                        continue

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
                        # Ensure task_done is called in all cases
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

            logger.info(f"Agent {self.agent_id} cleanup completed")

    # Note: We can remove join_network as it's not required for MVP
    # The registry handles all agent discovery and communication
    # If you want to keep it for future network functionality, here's the implementation:

    async def join_network(self, network):  # type: ignore
        """Join an agent network for agent-to-agent communication"""
        self.network = network
        await network.register_agent(self)
        # Broadcast availability with capabilities
        await network.broadcast_availability(self.agent_id, self.metadata.capabilities)

    def set_cooldown(self, duration: int) -> None:
        """Set a cooldown period for the agent"""
        self.cooldown_until = time.time() + duration

    def is_in_cooldown(self) -> bool:
        """Check if agent is in cooldown"""
        return time.time() < self.cooldown_until

    def end_conversation(self, other_agent_id: str) -> None:
        """End conversation with another agent"""
        if other_agent_id in self.active_conversations:
            # Log final conversation stats
            conversation_data = self.active_conversations[other_agent_id]
            conversation_duration = time.time() - conversation_data.get("start_time", 0)
            message_count = conversation_data.get("message_count", 0)

            logger.info(
                f"Ending conversation between {self.agent_id} and {other_agent_id}. "
                f"Duration: {int(conversation_duration)}s, Messages: {message_count}"
            )

            # Clean up conversation data
            del self.active_conversations[other_agent_id]

    async def can_send_message(self, receiver_id: str) -> bool:
        """Check if agent can send message"""
        if self.is_in_cooldown():
            return False
        if receiver_id not in self.active_conversations:
            self.active_conversations[receiver_id] = {
                "start_time": time.time(),
                "message_count": 0,
            }
        return True

    async def can_receive_message(self, sender_id: str) -> bool:
        """Check if the agent can receive a message from the sender"""
        if self.is_in_cooldown():
            return False
        if sender_id not in self.active_conversations:
            return True
        # Add any other conditions as needed
        return True
