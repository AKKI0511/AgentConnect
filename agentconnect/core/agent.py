"""
Base agent implementation for the AgentConnect framework.

This module provides the abstract base class for all agents in the system,
defining the core functionality for agent identity, messaging, and interaction.
"""

import asyncio
import logging
import time

# Standard library imports
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agentconnect.core.exceptions import SecurityError

# Absolute imports from agentconnect package
from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentIdentity,
    AgentMetadata,
    AgentType,
    Capability,
    InteractionMode,
    MessageType,
    VerificationStatus,
)

# Type checking imports
if TYPE_CHECKING:
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.registry import AgentRegistry

# Set up logging
logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    This class defines the core functionality that all agents must implement,
    including identity verification, message handling, and conversation management.

    Attributes:
        agent_id: Unique identifier for the agent
        identity: Agent's decentralized identity
        metadata: Metadata about the agent
        capabilities: List of agent capabilities
        message_queue: Queue for incoming messages
        message_history: History of messages sent and received
        is_running: Whether the agent is currently running
        registry: Reference to the agent registry
        hub: Reference to the communication hub
        active_conversations: Dictionary of active conversations
        cooldown_until: Timestamp when cooldown ends
        pending_requests: Dictionary of pending requests
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        identity: AgentIdentity,
        interaction_modes: List[InteractionMode],
        capabilities: List[Capability] = None,
        organization_id: Optional[str] = None,
    ):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of agent (human, AI)
            identity: Agent's decentralized identity
            interaction_modes: Supported interaction modes
            capabilities: List of agent capabilities
            organization_id: ID of the organization the agent belongs to
        """
        self.agent_id = agent_id
        self.identity = identity
        self.metadata = AgentMetadata(
            agent_id=agent_id,
            agent_type=agent_type,
            identity=identity,
            organization_id=organization_id,
            capabilities=[cap.name for cap in capabilities] if capabilities else [],
            interaction_modes=interaction_modes,
        )
        self.capabilities = capabilities or []
        self.message_queue = asyncio.Queue()
        self.message_history: List[Message] = []
        self.is_running = False
        self.registry: Optional["AgentRegistry"] = None
        self.hub: Optional["CommunicationHub"] = None
        self.active_conversations = {}
        self.cooldown_until = 0
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        logger.info(f"Agent {self.agent_id} ({agent_type}) initialized.")

    @abstractmethod
    def _initialize_llm(self):
        """
        Initialize the language model for the agent.

        This method must be implemented by subclasses to initialize
        the language model used by the agent.

        Returns:
            The initialized language model
        """
        pass

    @abstractmethod
    def _initialize_workflow(self):
        """
        Initialize the workflow for the agent.

        This method must be implemented by subclasses to initialize
        the workflow used by the agent for processing messages.

        Returns:
            The initialized workflow
        """
        pass

    async def _verify_ethereum_did(self) -> bool:
        """
        Verify Ethereum-based DID.

        This method verifies the agent's Ethereum-based decentralized identifier.

        Returns:
            True if the DID is valid, False otherwise
        """
        logger.debug(f"Agent {self.agent_id}: Verifying Ethereum DID.")
        try:
            # Here you would typically:
            # 1. Resolve the DID document from Ethereum
            # 2. Verify the public key matches the DID
            # 3. Verify the key can sign/verify messages

            # For MVP, we'll do basic format verification
            # TODO: Implement full Ethereum DID verification
            logger.debug(
                f"Agent {self.agent_id}: Basic Ethereum DID verification passed (placeholder)."
            )
            return True
        except Exception as e:
            logger.error(
                f"Agent {self.agent_id}: Error verifying Ethereum DID: {str(e)}"
            )
            return False

    async def _verify_key_did(self) -> bool:
        """
        Verify key-based DID.

        This method verifies the agent's key-based decentralized identifier.

        Returns:
            True if the DID is valid, False otherwise
        """
        logger.debug(f"Agent {self.agent_id}: Verifying key-based DID.")
        try:
            # Here you would typically:
            # 1. Decode the multibase-encoded public key
            # 2. Verify it matches the stored public key
            # 3. Verify the key can sign/verify messages

            # For MVP, we'll do basic format verification
            # TODO: Implement full key-based DID verification
            logger.debug(
                f"Agent {self.agent_id}: Basic key-based DID verification passed (placeholder)."
            )
            return True
        except Exception as e:
            logger.error(
                f"Agent {self.agent_id}: Error verifying key-based DID: {str(e)}"
            )
            return False

    async def verify_identity(self) -> bool:
        """
        Verify agent's DID and update verification status.

        This method verifies the agent's decentralized identifier and
        updates the verification status accordingly.

        Returns:
            True if the identity is verified, False otherwise

        Raises:
            SecurityError: If identity verification fails
        """
        logger.debug(f"Agent {self.agent_id}: Verifying identity.")
        try:
            # Verify DID using did:ethr or did:key
            if self.identity.did.startswith("did:ethr:"):
                verified = await self._verify_ethereum_did()
            elif self.identity.did.startswith("did:key:"):
                verified = await self._verify_key_did()
            else:
                error_msg = f"Unsupported DID method: {self.identity.did}"
                logger.error(f"Agent {self.agent_id}: {error_msg}")
                raise ValueError(error_msg)

            self.identity.verification_status = (
                VerificationStatus.VERIFIED if verified else VerificationStatus.FAILED
            )
            logger.info(
                f"Agent {self.agent_id}: Identity verification status: {self.identity.verification_status}"
            )
            return verified
        except Exception as e:
            self.identity.verification_status = VerificationStatus.FAILED
            error_msg = f"Identity verification failed: {e}"
            logger.error(f"Agent {self.agent_id}: {error_msg}")
            raise SecurityError(error_msg)

    async def send_message(
        self,
        receiver_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
    ) -> Message:
        """
        Create and send a message through the hub.

        Args:
            receiver_id: ID of the receiving agent
            content: Message content
            message_type: Type of message being sent
            metadata: Additional information about the message

        Returns:
            The sent message

        Raises:
            RuntimeError: If the agent is not registered with a hub
            ValueError: If the message cannot be routed
        """
        logger.info(
            f"Agent {self.agent_id} sending message to {receiver_id}: {content[:50]}..."
        )
        if not self.hub:
            error_msg = "Agent not registered with hub"
            logger.error(f"Agent {self.agent_id}: {error_msg}")
            raise RuntimeError(error_msg)

        # Check if this is a response to a pending request
        if not metadata:
            metadata = {}

        # If we have a pending request from this receiver, this is likely a response
        if hasattr(self, "pending_requests") and receiver_id in self.pending_requests:
            request_data = self.pending_requests[receiver_id]
            if "request_id" in request_data:
                # Add response correlation
                metadata["response_to"] = request_data["request_id"]
                # Clean up the pending request
                del self.pending_requests[receiver_id]
                logger.debug(
                    f"Agent {self.agent_id}: Added response correlation to message. Request ID: {request_data['request_id']}"
                )

        # Create the message
        message = Message.create(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            content=content,
            sender_identity=self.identity,
            message_type=message_type,
            metadata=metadata,
        )
        logger.debug(f"Agent {self.agent_id}: Message created.")

        # Send through hub instead of directly to receiver
        if not await self.hub.route_message(message):
            error_msg = "Failed to route message"
            logger.error(f"Agent {self.agent_id}: {error_msg}")
            raise ValueError(error_msg)

        self.message_history.append(message)
        logger.debug(f"Agent {self.agent_id}: Message sent and added to history.")
        return message

    async def receive_message(self, message: Message):
        """
        Receive and queue a message.

        Args:
            message: The message to receive
        """
        logger.info(
            f"Agent {self.agent_id} received message from {message.sender_id}: {message.content[:50]}..."
        )
        # Add the message to the queue and history
        await self.message_queue.put(message)
        self.message_history.append(message)
        logger.debug(
            f"Agent {self.agent_id}: Message received and added to queue and history."
        )

    @abstractmethod
    async def process_message(self, message: Message) -> Optional[Message]:
        """
        Process incoming message - must be implemented by subclasses.

        This method processes an incoming message and generates a response.
        It must be implemented by subclasses to provide agent-specific
        message processing logic.

        Args:
            message: The message to process

        Returns:
            Optional response message
        """
        logger.info(
            f"Agent {self.agent_id} processing message from {message.sender_id}: {message.content[:50]}..."
        )

        # Check if this is a collaboration request
        is_collaboration_request = (
            message.message_type == MessageType.REQUEST_COLLABORATION
        )

        # Verify message signature
        if not message.verify(self.identity):
            error_msg = "Message verification failed"
            logger.error(f"Agent {self.agent_id}: {error_msg}")

            # Determine the appropriate message type based on the request type
            message_type = (
                MessageType.COLLABORATION_RESPONSE
                if is_collaboration_request
                else MessageType.ERROR
            )

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=error_msg,
                sender_identity=self.identity,
                message_type=message_type,
                metadata={
                    "error_type": "verification_failed",
                    **(
                        {"original_message_type": "ERROR"}
                        if is_collaboration_request
                        else {}
                    ),
                },
            )

        # Check if agent can receive the message
        if not await self.can_receive_message(message.sender_id):
            logger.warning(
                f"Agent {self.agent_id} is in cooldown. Deferring message from {message.sender_id}."
            )
            # Send cooldown message back to the sender
            cooldown_duration = self.cooldown_until - time.time()
            if cooldown_duration > 0:
                cooldown_msg = f"I am in cooldown for {int(cooldown_duration)} seconds. Please try again later."
                logger.info(
                    f"Agent {self.agent_id} sending cooldown message to {message.sender_id}: {cooldown_msg[:50]}..."
                )

                # Determine the appropriate message type based on the request type
                message_type = (
                    MessageType.COLLABORATION_RESPONSE
                    if is_collaboration_request
                    else MessageType.COOLDOWN
                )

                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content=cooldown_msg,
                    sender_identity=self.identity,
                    message_type=message_type,
                    metadata={
                        "cooldown_remaining": cooldown_duration,
                        **(
                            {"original_message_type": "COOLDOWN"}
                            if is_collaboration_request
                            else {}
                        ),
                    },
                )
            else:
                error_msg = "Cannot receive messages from this sender"
                logger.warning(f"Agent {self.agent_id}: {error_msg}")

                # Determine the appropriate message type based on the request type
                message_type = (
                    MessageType.COLLABORATION_RESPONSE
                    if is_collaboration_request
                    else MessageType.ERROR
                )

                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content=error_msg,
                    sender_identity=self.identity,
                    message_type=message_type,
                    metadata={
                        "error_type": "cannot_receive",
                        **(
                            {"original_message_type": "ERROR"}
                            if is_collaboration_request
                            else {}
                        ),
                    },
                )

        # Check if conversation should end
        conversation_data = self.active_conversations.get(message.sender_id, {})
        if (
            hasattr(self, "interaction_control")
            and conversation_data.get("message_count", 0)
            >= self.interaction_control.max_turns
        ):
            logger.info(
                f"Agent {self.agent_id} ending conversation with {message.sender_id} due to max turns reached."
            )
            self.end_conversation(message.sender_id)
            stop_msg = "Maximum conversation turns reached. Ending conversation."

            # Determine the appropriate message type based on the request type
            message_type = (
                MessageType.COLLABORATION_RESPONSE
                if is_collaboration_request
                else MessageType.STOP
            )

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=stop_msg,
                sender_identity=self.identity,
                message_type=message_type,
                metadata={
                    "reason": "max_turns_reached",
                    **(
                        {"original_message_type": "STOP"}
                        if is_collaboration_request
                        else {}
                    ),
                },
            )

        if message.message_type == MessageType.STOP or "__EXIT__" in message.content:
            logger.info(
                f"Agent {self.agent_id} ending conversation with {message.sender_id} due to STOP message or exit command."
            )
            self.end_conversation(message.sender_id)

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content="Conversation ended successfully.",
                sender_identity=self.identity,
                message_type=MessageType.IGNORE,
                metadata={
                    "reason": "conversation_ended",
                },
            )

        # Check if the message is a cooldown notification
        if message.message_type == MessageType.COOLDOWN:
            cooldown_duration = message.metadata.get("cooldown_remaining", 0)
            logger.info(
                f"Agent {self.agent_id} received cooldown message from {message.sender_id}. Cooldown duration: {cooldown_duration} seconds."
            )

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Acknowledged cooldown for {message.sender_id} for {cooldown_duration} seconds.",
                sender_identity=self.identity,
                message_type=MessageType.IGNORE,
                metadata={
                    "acknowledged_cooldown": cooldown_duration,
                },
            )

        # If this is a request that needs a response, track the request ID for correlation
        if message.metadata and "request_id" in message.metadata:
            request_id = message.metadata["request_id"]
            # Store the request_id to correlate with response
            if not hasattr(self, "pending_requests"):
                self.pending_requests = {}
            self.pending_requests[message.sender_id] = {"request_id": request_id}
            logger.debug(
                f"Agent {self.agent_id}: Stored request ID for correlation: {request_id}"
            )

        # If we get here, it's a regular message that should be processed by the subclass
        logger.debug(
            f"Agent {self.agent_id}: Passing message to subclass for processing."
        )
        return None

    async def run(self):
        """
        Start the agent's message processing loop.

        This method starts the agent's main processing loop, which continuously
        processes messages from the message queue until the agent is stopped.
        """
        self.is_running = True
        logger.info(f"Agent {self.agent_id} started processing loop")
        try:
            while self.is_running:
                try:
                    # Get the next message from the queue with a timeout
                    # This ensures the agent can periodically check if it should stop
                    # and also allows it to process other tasks
                    try:
                        message = await asyncio.wait_for(
                            self.message_queue.get(), timeout=0.1  # 100ms timeout
                        )
                        logger.debug(
                            f"Agent {self.agent_id}: Got message from queue: {message.content[:50]}..."
                        )

                        # Skip processing if the agent is stopping
                        if not self.is_running:
                            logger.info(
                                f"Agent {self.agent_id}: Skipping message processing as agent is stopping"
                            )
                            self.message_queue.task_done()
                            continue

                        # Process the message in a separate task to avoid blocking the run loop
                        asyncio.create_task(self._process_message_and_respond(message))

                    except asyncio.TimeoutError:
                        # No message received within timeout, continue the loop
                        await asyncio.sleep(0)  # Yield control to the event loop
                        continue

                except asyncio.CancelledError:
                    logger.info(
                        f"Agent {self.agent_id}: Message processing loop cancelled"
                    )
                    break
                except Exception as e:
                    logger.exception(
                        f"Agent {self.agent_id}: Unexpected error in message processing loop: {str(e)}"
                    )
                    # Continue processing other messages
                    if "message" in locals() and message:
                        self.message_queue.task_done()

        except asyncio.CancelledError:
            logger.info(f"Agent {self.agent_id}: Run loop cancelled")
        except Exception as e:
            logger.exception(
                f"Agent {self.agent_id}: Unexpected error in run loop: {str(e)}"
            )
        finally:
            self.is_running = False
            logger.info(f"Agent {self.agent_id} stopped processing loop")

    async def _process_message_and_respond(self, message):
        """
        Process a message and send a response if needed.

        Args:
            message: The message to process
        """
        try:
            # Normal message processing
            response = await self.process_message(message)

            # If we got a response, send it back
            if response and response.message_type != MessageType.IGNORE:
                logger.debug(
                    f"Agent {self.agent_id}: Sending response to {message.sender_id}"
                )
                await self.send_message(
                    receiver_id=response.receiver_id,
                    content=response.content,
                    message_type=response.message_type,
                    metadata=response.metadata,
                )
        except Exception as e:
            logger.error(f"Agent {self.agent_id}: Error processing message: {str(e)}")

            # Find the original human sender in the conversation chain
            human_sender = await self._find_human_in_conversation_chain(
                message.sender_id
            )

            if human_sender:
                # Send error message to the human
                error_message = f"I encountered an error while processing your request: {str(e)}\n\nPlease try a different approach or simplify your request."
                await self.send_message(
                    receiver_id=human_sender,
                    content=error_message,
                    message_type=MessageType.ERROR,
                    metadata={"error_type": "processing_error"},
                )
                logger.info(
                    f"Agent {self.agent_id}: Sent error message to human {human_sender}"
                )

        # Mark the message as done
        self.message_queue.task_done()

    async def _find_human_in_conversation_chain(self, agent_id: str) -> Optional[str]:
        """
        Find the human agent in the conversation chain.

        Args:
            agent_id: ID of the agent to start the search from

        Returns:
            ID of the human agent if found, None otherwise
        """
        try:
            # If the sender is already a human, return it
            if agent_id.startswith("human_"):
                return agent_id

            # Otherwise, check active conversations to find a human
            for participant_id, conversation in self.active_conversations.items():
                if participant_id.startswith("human_"):
                    return participant_id

            # If no human found in direct conversations, return None
            return None
        except Exception as e:
            logger.error(f"Error finding human in conversation chain: {str(e)}")
            return None

    async def join_network(self, network):  # type: ignore
        """
        Join an agent network for agent-to-agent communication.

        Note: Join_network is not required for MVP
        The registry handles all agent discovery and communication
        We keep it for future network functionality

        Args:
            network: The network to join
        """
        logger.info(f"Agent {self.agent_id} joining network.")
        self.network = network
        await network.register_agent(self)
        # Broadcast availability with capabilities
        await network.broadcast_availability(self.agent_id, self.metadata.capabilities)
        logger.info(f"Agent {self.agent_id} broadcasted availability.")

    def set_cooldown(self, duration: int) -> None:
        """
        Set a cooldown period for the agent.

        Args:
            duration: Cooldown duration in seconds
        """
        self.cooldown_until = time.time() + duration
        logger.info(f"Agent {self.agent_id} set cooldown for {duration} seconds.")

    def is_in_cooldown(self) -> bool:
        """
        Check if agent is in cooldown.

        Returns:
            True if the agent is in cooldown, False otherwise
        """
        cooldown_status = time.time() < self.cooldown_until
        logger.debug(f"Agent {self.agent_id} cooldown status: {cooldown_status}")
        return cooldown_status

    def end_conversation(self, other_agent_id: str) -> None:
        """
        End conversation with another agent.

        Args:
            other_agent_id: ID of the other agent in the conversation
        """
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
            logger.debug(
                f"Agent {self.agent_id}: Ended conversation with {other_agent_id}."
            )

    async def can_send_message(self, receiver_id: str) -> bool:
        """
        Check if agent can send message.

        Args:
            receiver_id: ID of the receiving agent

        Returns:
            True if the agent can send a message, False otherwise
        """
        if self.is_in_cooldown():
            logger.debug(
                f"Agent {self.agent_id} cannot send message to {receiver_id}: in cooldown."
            )
            return False
        if receiver_id not in self.active_conversations:
            self.active_conversations[receiver_id] = {
                "start_time": time.time(),
                "message_count": 0,
            }
            logger.debug(
                f"Agent {self.agent_id}: Started new conversation with {receiver_id}."
            )
        logger.debug(f"Agent {self.agent_id} can send message to {receiver_id}.")
        return True

    async def can_receive_message(self, sender_id: str) -> bool:
        """
        Check if the agent can receive a message from the sender.

        Args:
            sender_id: ID of the sending agent

        Returns:
            True if the agent can receive a message, False otherwise
        """
        if self.is_in_cooldown():
            cooldown_remaining = self.cooldown_until - time.time()
            logger.warning(
                f"Agent {self.agent_id} cannot receive message from {sender_id}: in cooldown for {int(cooldown_remaining)} more seconds."
            )
            return False
        if sender_id not in self.active_conversations:
            logger.debug(
                f"Agent {self.agent_id}: New conversation detected with {sender_id}."
            )
            return True
        # Add any other conditions as needed
        logger.debug(f"Agent {self.agent_id} can receive message from {sender_id}.")
        return True

    def reset_cooldown(self) -> None:
        """
        Reset the cooldown state of the agent.

        This method resets the agent's cooldown state, allowing it to
        send and receive messages immediately.
        """
        previous_cooldown = (
            self.cooldown_until - time.time() if self.is_in_cooldown() else 0
        )
        self.cooldown_until = 0
        logger.info(
            f"Agent {self.agent_id} cooldown reset. Previous remaining cooldown: {int(previous_cooldown)} seconds."
        )

    def _get_conversation_id(self, participant_id: str) -> str:
        """
        Generate a unique conversation ID based on both participants.

        Args:
            participant_id: ID of the other participant

        Returns:
            A unique conversation ID
        """
        # Create a directed conversation ID to ensure unique conversations
        # This ensures that A->B and B->A are different conversations
        conversation_id = f"conversation_{self.agent_id}_to_{participant_id}"
        logger.debug(f"Generated conversation ID: {conversation_id}")
        return conversation_id
