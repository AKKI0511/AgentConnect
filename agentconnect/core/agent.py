"""
Base agent implementation for the AgentConnect framework.

This module provides the abstract base class for all agents in the system,
defining the core functionality for agent identity, messaging, and interaction.
"""

from __future__ import annotations

import asyncio
import logging
import time

# Standard library imports
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast
from pathlib import Path
from dotenv import load_dotenv

# Absolute imports from agentconnect package
from agentconnect.utils import wallet_manager
from agentconnect.core.exceptions import SecurityError
from agentconnect.core.message import Message
from agentconnect.config import settings as global_settings
from agentconnect.core.types import (
    AgentIdentity,
    AgentProfile,
    InteractionMode,
    MessageType,
    VerificationStatus,
)

# Type checking imports
if TYPE_CHECKING:
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.registry import AgentRegistry

    # Optional payment types (for static typing and IDEs only)
    from coinbase_agentkit import AgentKit as _AgentKit  # type: ignore
    from coinbase_agentkit import CdpWalletProvider as _CdpWalletProvider  # type: ignore

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
        profile: Comprehensive profile for the agent
        capabilities: List of agent capabilities
        message_queue: Queue for incoming messages
        message_history: History of messages sent and received
        is_running: Whether the agent is currently running
        registry: Reference to the agent registry
        hub: Reference to the communication hub
        active_conversations: Dictionary of active conversations
        cooldown_until: Timestamp when cooldown ends
        pending_requests: Dictionary of pending requests
        enable_payments: Whether payment capabilities are enabled
        wallet_provider: Wallet provider for blockchain transactions
        agent_kit: AgentKit instance for blockchain actions
    """

    def __init__(
        self,
        agent_id: str,
        identity: AgentIdentity,
        interaction_modes: List[InteractionMode],
        profile: AgentProfile,
        enable_payments: bool = False,
        wallet_data_dir: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for the agent
            identity: Agent's decentralized identity
            interaction_modes: Supported interaction modes
            profile: Comprehensive agent profile (provided by the subclass)
            enable_payments: Whether to enable payment capabilities
            wallet_data_dir: Optional custom directory for wallet data storage
        """
        self.agent_id = agent_id
        self.identity = identity
        self.interaction_modes = interaction_modes
        self.profile = profile

        # Ensure self.capabilities points to the profile's capabilities
        self.capabilities = self.profile.capabilities

        # Track whether we've emitted a one-time verified INFO log
        self._verified_logged_once: bool = False

        self.message_queue = asyncio.Queue()
        self.message_history: List[Message] = []
        self.is_running = False
        self.registry: Optional["AgentRegistry"] = None
        self.hub: Optional["CommunicationHub"] = None
        self.active_conversations = {}
        self.cooldown_until = 0
        self.pending_requests: Dict[str, Dict[str, Any]] = {}

        # Initialize payment capabilities (avoid optional type names at import time)
        self.enable_payments = enable_payments
        self.wallet_provider: Optional[_CdpWalletProvider] = None
        self.agent_kit: Optional[_AgentKit] = None

        # Initialize wallet if payments are enabled
        if self.enable_payments:
            try:
                # Load environment variables
                load_dotenv()

                # Check if this agent already has wallet data
                wallet_data = wallet_manager.load_wallet_data(
                    self.agent_id, wallet_data_dir
                )

                # Import optional dependencies lazily to avoid hard import requirements
                from coinbase_agentkit import (  # type: ignore
                    AgentKit,
                    AgentKitConfig,
                    CdpWalletProvider,
                    CdpWalletProviderConfig,
                    wallet_action_provider,
                    erc20_action_provider,
                    cdp_api_action_provider,
                )

                # Initialize wallet provider via coinbase CDP-SDK
                cdp_config = (
                    CdpWalletProviderConfig(wallet_data=wallet_data)
                    if wallet_data
                    else None
                )
                self.wallet_provider = cast(
                    "_CdpWalletProvider", CdpWalletProvider(cdp_config)
                )

                # Prepare action providers based on the token symbol
                action_providers = [wallet_action_provider(), cdp_api_action_provider()]

                # Add ERC20 action provider if using tokens other than native ETH
                payment_symbol = global_settings.payments.default_token_symbol
                if payment_symbol != "ETH":
                    action_providers.append(erc20_action_provider())

                # Initialize coinbase AgentKit with wallet provider and action providers
                agent_kit_config = AgentKitConfig(
                    wallet_provider=self.wallet_provider,
                    action_providers=action_providers,
                )
                self.agent_kit = cast("_AgentKit", AgentKit(agent_kit_config))

                # Save wallet data if it's a new wallet
                if not wallet_data:
                    try:
                        new_wallet_data = self.wallet_provider.export_wallet()
                        wallet_manager.save_wallet_data(
                            self.agent_id, new_wallet_data, wallet_data_dir
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to persist new wallet data agent_id=%s: %s",
                            self.agent_id,
                            e,
                        )

                # Get wallet address and add to agent profile
                try:
                    # Get the default wallet address
                    wallet_address = self.wallet_provider.get_address()
                    if wallet_address:
                        self.profile.payment_address = wallet_address
                    else:
                        logger.warning(
                            "Wallet address unavailable agent_id=%s", self.agent_id
                        )
                except Exception as e:
                    logger.error(
                        "Error retrieving wallet address agent_id=%s: %s",
                        self.agent_id,
                        e,
                    )
            except Exception as e:
                logger.error(
                    "Error initializing payment capabilities agent_id=%s: %s",
                    self.agent_id,
                    e,
                )
                self.wallet_provider = None
                self.agent_kit = None
                logger.warning(
                    "Payment capabilities disabled agent_id=%s", self.agent_id
                )
        # Minimal: no DEBUG agent.init ok on construction

    @property
    def payments_enabled(self) -> bool:
        """
        Check if payment capabilities are enabled and available.

        Returns:
            True if payment capabilities are enabled and available, False otherwise
        """
        return self.enable_payments and self.wallet_provider is not None

    async def _verify_ethereum_did(self) -> bool:
        """
        Verify Ethereum-based DID.

        This method verifies the agent's Ethereum-based decentralized identifier.

        Returns:
            True if the DID is valid, False otherwise
        """
        try:
            # Here you would typically:
            # 1. Resolve the DID document from Ethereum
            # 2. Verify the public key matches the DID
            # 3. Verify the key can sign/verify messages

            # For MVP, we'll do basic format verification
            # TODO: Implement full Ethereum DID verification
            return True
        except Exception as e:
            logger.error(
                "Error verifying Ethereum DID agent_id=%s: %s", self.agent_id, e
            )
            return False

    async def _verify_key_did(self) -> bool:
        """
        Verify key-based DID.

        This method verifies the agent's key-based decentralized identifier.

        Returns:
            True if the DID is valid, False otherwise
        """
        try:
            # Here you would typically:
            # 1. Decode the multibase-encoded public key
            # 2. Verify it matches the stored public key
            # 3. Verify the key can sign/verify messages

            # For MVP, we'll do basic format verification
            # TODO: Implement full key-based DID verification
            return True
        except Exception as e:
            logger.error(
                "Error verifying key-based DID agent_id=%s: %s", self.agent_id, e
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
        # Skip re-verification noise when already VERIFIED; allow explicit re-verify at DEBUG only
        if self.identity.verification_status == VerificationStatus.VERIFIED:
            return True
        try:
            # Verify DID using did:ethr or did:key
            if self.identity.did.startswith("did:ethr:"):
                verified = await self._verify_ethereum_did()
            elif self.identity.did.startswith("did:key:"):
                verified = await self._verify_key_did()
            else:
                raise ValueError("Unsupported DID method")

            self.identity.verification_status = (
                VerificationStatus.VERIFIED if verified else VerificationStatus.FAILED
            )
            if verified:
                if not self._verified_logged_once:
                    logger.info("Identity verified agent_id=%s", self.agent_id)
                    self._verified_logged_once = True
            return verified
        except Exception:  # pylint: disable=broad-exception-raised
            self.identity.verification_status = VerificationStatus.FAILED
            raise SecurityError("Identity verification failed")

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
        request_id = None
        start_ts = time.time()
        if metadata:
            request_id = metadata.get("request_id")

        if not self.hub:
            # Log sending failure succinctly
            logger.error(
                "Cannot send: not registered with hub agent_id=%s receiver_id=%s type=%s request_id=%s",
                self.agent_id,
                receiver_id,
                message_type.value,
                request_id,
            )
            raise RuntimeError("Agent not registered with hub")

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
                # Include correlation id for logging purposes
                request_id = request_data.get("request_id", request_id)

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
        try:
            success = await self.hub.route_message(message)
        except Exception as e:
            logger.error(
                "Route error agent_id=%s receiver_id=%s type=%s request_id=%s duration=%dms: %s",
                self.agent_id,
                receiver_id,
                message_type.value,
                request_id,
                int((time.time() - start_ts) * 1000.0),
                e,
            )
            raise

        if not success:
            logger.error(
                "Failed to route message agent_id=%s receiver_id=%s type=%s request_id=%s",
                self.agent_id,
                receiver_id,
                message_type.value,
                request_id,
            )
            raise ValueError("Failed to route message")

        self.message_history.append(message)
        # Do not log BaseAgent send ok; hub emits hub.delivery ok
        return message

    async def receive_message(self, message: Message):
        """
        Receive and queue a message.

        Args:
            message: The message to receive
        """
        # Queue inbound message and record history; no noisy success logs
        await self.message_queue.put(message)
        self.message_history.append(message)

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

        # Check if this is a collaboration request
        is_collaboration_request = (
            message.message_type == MessageType.REQUEST_COLLABORATION
        )

        # Verify message signature
        if not message.verify(self.identity):
            error_msg = "Message verification failed"
            logger.error(
                "%s agent_id=%s sender_id=%s type=%s request_id=%s",
                error_msg,
                self.agent_id,
                message.sender_id,
                message.message_type.value,
                (message.metadata or {}).get("request_id"),
            )

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
            # Compute remaining seconds for concise warning
            cooldown_duration = self.cooldown_until - time.time()
            logger.warning(
                "Cooldown active; deferring receive; %ds remaining agent_id=%s sender_id=%s",
                int(max(cooldown_duration, 0)),
                self.agent_id,
                message.sender_id,
            )
            # Send cooldown message back to the sender
            if cooldown_duration > 0:
                cooldown_msg = f"I am in cooldown for {int(cooldown_duration)} seconds. Please try again later."
                # No BaseAgent send-ok/start logging; hub will emit delivery success

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
                logger.warning(
                    "%s agent_id=%s sender_id=%s",
                    error_msg,
                    self.agent_id,
                    message.sender_id,
                )

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

        # If we get here, it's a regular message that should be processed by the subclass
        return None

    async def run(self):
        """
        Start the agent's message processing loop.

        This method starts the agent's main processing loop, which continuously
        processes messages from the message queue until the agent is stopped.
        """
        self.is_running = True
        logger.info("Run loop start agent_id=%s", self.agent_id)
        try:
            while self.is_running:
                try:
                    # Get the next message from the queue with a timeout
                    # This ensures the agent can periodically check if it should stop
                    # and also allows it to process other tasks
                    try:
                        message: Message = await asyncio.wait_for(
                            self.message_queue.get(), timeout=0.1  # 100ms timeout
                        )

                        # Skip processing if the agent is stopping; avoid per-iteration noise
                        if not self.is_running:
                            self.message_queue.task_done()
                            continue

                        # Process the message in a separate task to avoid blocking the run loop
                        asyncio.create_task(self._process_message_and_respond(message))

                    except asyncio.TimeoutError:
                        # No message received within timeout, continue the loop
                        await asyncio.sleep(0)  # Yield control to the event loop
                        continue

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(
                        "Unexpected error in message processing loop agent_id=%s: %s",
                        self.agent_id,
                        e,
                    )
                    # Continue processing other messages
                    if "message" in locals() and message:
                        self.message_queue.task_done()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error in run loop agent_id=%s: %s", self.agent_id, e
            )
        finally:
            # TODO: Stop agent directly when refactoring `BaseAgent`
            self.is_running = False
            logger.info("Run loop stop agent_id=%s", self.agent_id)

    async def _process_message_and_respond(self, message: Message):
        """
        Process a message and send a response if needed.

        Args:
            message: The message to process
        """
        start_ts = time.time()
        try:
            # Normal message processing
            response = await self.process_message(message)

            # If we got a response, send it back
            response_sent = False
            if response and response.message_type != MessageType.IGNORE:
                await self.send_message(
                    receiver_id=response.receiver_id,
                    content=response.content,
                    message_type=response.message_type,
                    metadata=response.metadata,
                )
                response_sent = True
            # Emit a single DEBUG success for inbound processing, including request and response types
            response_type = response.message_type.value if response else None
            logger.debug(
                "Message processed agent_id=%s sender_id=%s request_type=%s response_type=%s request_id=%s duration=%dms response_sent=%s",
                self.agent_id,
                message.sender_id,
                message.message_type.value,
                response_type,
                (message.metadata or {}).get("request_id"),
                int((time.time() - start_ts) * 1000.0),
                "yes" if response_sent else "no",
            )
        except Exception as e:
            logger.error(
                "Error processing message agent_id=%s sender_id=%s type=%s request_id=%s duration=%dms",
                self.agent_id,
                message.sender_id,
                message.message_type.value,
                (message.metadata or {}).get("request_id"),
                int((time.time() - start_ts) * 1000.0),
                exc_info=True,
            )

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
            logger.error(
                "Error finding human in conversation chain agent_id=%s: %s",
                self.agent_id,
                e,
            )
            return None

    async def join_network(self, network):
        """
        Join an agent network for agent-to-agent communication.

        Note: Join_network is not required for MVP
        The registry handles all agent discovery and communication
        We keep it for future network functionality

        Args:
            network: The network to join

        Returns:
            True if successfully joined, False otherwise
        """
        self.network = network
        await network.register_agent(self)
        # Broadcast availability with capabilities
        await network.broadcast_availability(self.agent_id, self.profile.capabilities)

    def set_cooldown(self, duration: int) -> None:
        """
        Set a cooldown period for the agent.

        Args:
            duration: Cooldown duration in seconds
        """
        self.cooldown_until = time.time() + duration
        logger.debug("Cooldown set; %ds remaining agent_id=%s", duration, self.agent_id)

    def is_in_cooldown(self) -> bool:
        """
        Check if agent is in cooldown.

        Returns:
            True if the agent is in cooldown, False otherwise
        """
        cooldown_status = time.time() < self.cooldown_until
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

            # Log duration in seconds, minutes, or hours for clarity
            if conversation_duration < 60:
                duration_str = f"{conversation_duration:.2f}s"
            elif conversation_duration < 3600:
                duration_str = f"{conversation_duration/60:.2f}min"
            else:
                duration_str = f"{conversation_duration/3600:.2f}h"

            logger.debug(
                "Conversation ended agent_id=%s receiver_id=%s messages=%d duration=%s",
                self.agent_id,
                other_agent_id,
                message_count,
                duration_str,
            )

            # Clean up conversation data
            del self.active_conversations[other_agent_id]

    async def can_send_message(self, receiver_id: str) -> bool:
        """
        Check if agent can send message.

        Args:
            receiver_id: ID of the receiving agent

        Returns:
            True if the agent can send a message, False otherwise
        """
        if self.is_in_cooldown():
            logger.warning(
                "Cannot send: cooldown active agent_id=%s receiver_id=%s",
                self.agent_id,
                receiver_id,
            )
            return False
        if receiver_id not in self.active_conversations:
            self.active_conversations[receiver_id] = {
                "start_time": time.time(),
                "message_count": 0,
            }
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
                "Cannot receive: cooldown active; %ds remaining agent_id=%s sender_id=%s",
                int(max(cooldown_remaining, 0)),
                self.agent_id,
                sender_id,
            )
            return False
        if sender_id not in self.active_conversations:
            return True
        # Add any other conditions as needed
        return True

    async def stop(self) -> None:
        """
        Stop the agent and cleanup resources.

        This method stops the agent's processing loop, ends all active conversations,
        and cleans up resources such as wallet providers and message queues.

        Returns:
            None
        """
        # Mark agent as not running to stop the message processing loop
        self.is_running = False

        # End all active conversations
        for participant_id in list(self.active_conversations.keys()):
            self.end_conversation(participant_id)

        # Clean up wallet provider if it exists
        if self.wallet_provider is not None:
            try:
                # Clean up any pending transactions or listeners
                # Note: Additional cleanup may be needed depending on wallet implementation
                self.wallet_provider = None
                self.agent_kit = None
            except Exception as e:
                logger.error(
                    "Error cleaning up wallet provider agent_id=%s: %s",
                    self.agent_id,
                    e,
                )

        # Clear message queue to prevent processing any more messages
        try:
            while not self.message_queue.empty():
                self.message_queue.get_nowait()
                self.message_queue.task_done()
        except Exception as e:
            logger.error(
                "Error clearing message queue agent_id=%s: %s", self.agent_id, e
            )

        # Reset cooldown
        self.reset_cooldown()

        # Clear pending requests
        self.pending_requests.clear()

    def reset_cooldown(self) -> None:
        """
        Reset the cooldown state of the agent.

        This method resets the agent's cooldown state, allowing it to
        send and receive messages immediately.
        """
        # Track previous cooldown internally if needed in the future
        self.cooldown_until = 0

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
        return conversation_id
