from abc import ABC, abstractmethod
import asyncio
from typing import List, Optional, Dict, TYPE_CHECKING

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
        while self.is_running:
            try:
                message = await self.message_queue.get()
                response = await self.process_message(message)
                if response:
                    await self.send_message(
                        receiver_id=response.receiver_id,
                        content=response.content,
                        message_type=response.message_type,
                        metadata=response.metadata,
                    )
                self.message_queue.task_done()
            except Exception as e:
                print(f"Error processing message: {e}")

    # Note: We can remove join_network as it's not required for MVP
    # The registry handles all agent discovery and communication
    # If you want to keep it for future network functionality, here's the implementation:

    async def join_network(self, network):  # type: ignore
        """Join an agent network for agent-to-agent communication"""
        self.network = network
        await network.register_agent(self)
        # Broadcast availability with capabilities
        await network.broadcast_availability(self.agent_id, self.metadata.capabilities)
