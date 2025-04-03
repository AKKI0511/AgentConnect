"""
Independent AI Agent implementation for the AgentConnect decentralized framework.

This module provides an autonomous AI agent that can operate independently within a decentralized
network, process messages, generate responses, discover other agents based on capabilities,
and interact with those agents without pre-defined connections or central control.
Each agent can potentially implement its own internal multi-agent structure while maintaining
secure communication with other agents in the decentralized network.
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

# Absolute imports from agentconnect package
from agentconnect.core.agent import BaseAgent
from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentIdentity,
    AgentType,
    Capability,
    InteractionMode,
    MessageType,
    ModelName,
    ModelProvider,
)
from agentconnect.prompts.agent_prompts import create_workflow_for_agent
from agentconnect.prompts.templates.prompt_templates import (
    PromptTemplates,
    SystemPromptConfig,
)
from agentconnect.prompts.tools import PromptTools
from agentconnect.utils.interaction_control import (
    InteractionControl,
    InteractionState,
    TokenConfig,
)

# Set up logging
logger = logging.getLogger(__name__)


# Simple enum for memory types
class MemoryType(str, Enum):
    """Types of memory storage backends."""

    BUFFER = "buffer"  # In-memory buffer


class AIAgent(BaseAgent):
    """
    Independent AI Agent implementation that operates autonomously in a decentralized network.

    This agent uses language models to generate responses, can discover and communicate with
    other agents based on their capabilities (not pre-defined connections), and can implement
    its own internal multi-agent structure if needed. It operates as a peer in a decentralized
    system rather than as part of a centrally controlled hierarchy.

    Key features:

    - Autonomous operation with independent decision-making
    - Capability-based discovery of other agents
    - Secure identity verification and communication
    - Potential for internal multi-agent structures
    - Dynamic request routing based on capabilities
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        provider_type: ModelProvider,
        model_name: ModelName,
        api_key: str,
        identity: AgentIdentity,
        capabilities: List[Capability] = None,
        personality: str = "helpful and professional",
        organization_id: Optional[str] = None,
        interaction_modes: List[InteractionMode] = [
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
        max_tokens_per_minute: int = 70000,
        max_tokens_per_hour: int = 700000,
        max_turns: int = 20,
        is_ui_mode: bool = False,
        memory_type: MemoryType = MemoryType.BUFFER,
        prompt_tools: Optional[PromptTools] = None,
        prompt_templates: Optional[PromptTemplates] = None,
        # Custom tools parameter
        custom_tools: Optional[List[BaseTool]] = None,
        agent_type: str = "ai",
    ):
        """Initialize the AI agent.

        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable name for the agent
            provider_type: Type of model provider (e.g., OpenAI, Anthropic)
            model_name: Name of the model to use
            api_key: API key for the model provider
            identity: Identity information for the agent
            capabilities: List of agent capabilities
            personality: Description of the agent's personality
            organization_id: ID of the organization the agent belongs to
            interaction_modes: List of supported interaction modes
            max_tokens_per_minute: Maximum tokens per minute for rate limiting
            max_tokens_per_hour: Maximum tokens per hour for rate limiting
            is_ui_mode: Whether the agent is running in UI mode
            memory_type: Type of memory storage to use
            prompt_tools: Optional tools for the agent
            prompt_templates: Optional prompt templates for the agent
            custom_tools: Optional list of custom LangChain tools for the agent
            agent_type: Type of agent workflow to create
        """
        # Initialize base agent
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.AI,
            identity=identity,
            capabilities=capabilities or [],
            organization_id=organization_id,
            interaction_modes=interaction_modes,
        )

        # Store agent-specific attributes
        self.name = name
        self.personality = personality
        self.last_processed_message_id = None
        self.provider_type = provider_type
        self.model_name = model_name
        self.api_key = api_key
        self.is_ui_mode = is_ui_mode
        self.memory_type = memory_type
        self.workflow_agent_type = agent_type

        # Store the custom tools list if provided
        self.custom_tools = custom_tools or []

        # Store the prompt_tools instance if provided
        self._prompt_tools = prompt_tools

        # Create a new PromptTemplates instance for this agent
        self.prompt_templates = prompt_templates or PromptTemplates()

        # Initialize token tracking and rate limiting
        token_config = TokenConfig(
            max_tokens_per_minute=max_tokens_per_minute,
            max_tokens_per_hour=max_tokens_per_hour,
        )

        self.interaction_control = InteractionControl(
            token_config=token_config, max_turns=max_turns
        )

        # Set cooldown callback to update agent's cooldown state
        self.interaction_control.set_cooldown_callback(self.set_cooldown)

        # Initialize the LLM
        self.llm = self._initialize_llm()
        logger.debug(f"Initialized LLM for AI Agent {self.agent_id}: {self.llm}")

        # Initialize the workflow to None - will be set when registry and hub are available
        self.workflow = None

        # Initialize the conversation chain (kept for consistency)
        self.conversation_chain = None

        logger.info(
            f"AI Agent {self.agent_id} initialized with {len(self.capabilities)} capabilities"
        )

    # Property setter for hub that initializes workflow when both hub and registry are set
    @property
    def hub(self):
        """Get the hub property."""
        return self._hub

    @hub.setter
    def hub(self, value):
        """Set the hub property."""
        self._hub = value
        self._initialize_workflow_if_ready()

    # Property setter for registry that initializes workflow when both hub and registry are set
    @property
    def registry(self):
        """Get the registry property."""
        return self._registry

    @registry.setter
    def registry(self, value):
        """Set the registry property."""
        self._registry = value
        self._initialize_workflow_if_ready()

    def _initialize_workflow_if_ready(self):
        """Initialize the workflow if both registry and hub are set."""
        if (
            hasattr(self, "_hub")
            and self._hub is not None
            and hasattr(self, "_registry")
            and self._registry is not None
        ):
            if self.workflow is None:
                logger.debug(
                    f"AI Agent {self.agent_id}: Registry and hub are set, initializing workflow"
                )
                self.workflow = self._initialize_workflow()
                logger.debug(f"AI Agent {self.agent_id}: Workflow initialized")

    def _initialize_workflow(self) -> Runnable:
        """Initialize the workflow for the agent."""

        # Create a new PromptTools instance for this agent if not provided
        if self._prompt_tools is None:
            self._prompt_tools = PromptTools(
                agent_registry=self.registry, communication_hub=self.hub, llm=self.llm
            )
            logger.debug(f"AI Agent {self.agent_id}: Created new PromptTools instance.")

        # Set the current agent context for the tools
        self._prompt_tools.set_current_agent(self.agent_id)
        logger.debug(f"AI Agent {self.agent_id}: Current agent context set in tools.")

        # Get the tools from PromptTools
        tools = self._prompt_tools
        logger.debug(f"AI Agent {self.agent_id}: Tools initialized or provided.")

        # Create prompt templates if not provided
        prompt_templates = self.prompt_templates or PromptTemplates()
        logger.debug(
            f"AI Agent {self.agent_id}: Prompt templates initialized or provided."
        )

        # Create system config - Pass the full Capability objects
        self.system_config = SystemPromptConfig(
            name=self.name,
            capabilities=self.capabilities,  # Pass full Capability objects
            personality=self.personality,
        )
        logger.debug(
            f"AI Agent {self.agent_id}: System config created with capabilities: {self.capabilities}"
        )

        # Create and compile the workflow with business logic info
        workflow = create_workflow_for_agent(
            agent_type=self.workflow_agent_type,
            system_config=self.system_config,
            llm=self.llm,
            tools=tools,
            prompt_templates=prompt_templates,
            agent_id=self.agent_id,
            custom_tools=self.custom_tools,  # Pass the custom tools list
        )
        logger.debug(
            f"AI Agent {self.agent_id}: Workflow created with {len(self.custom_tools)} custom tools."
        )

        compiled_workflow = workflow.compile()
        logger.debug(f"AI Agent {self.agent_id}: Workflow compiled.")
        return compiled_workflow

    def _initialize_llm(self):
        """Initialize the LLM based on the provider type and model name."""
        from agentconnect.providers import ProviderFactory

        provider = ProviderFactory.create_provider(self.provider_type, self.api_key)
        logger.debug(f"AI Agent {self.agent_id}: LLM provider created: {provider}")
        return provider.get_langchain_llm(model_name=self.model_name)

    async def process_message(self, message: Message) -> Optional[Message]:
        """
        Process an incoming message autonomously and generate a response.

        This method represents the agent's autonomous decision loop, where it:

        - Verifies message security independently
        - Makes decisions on how to respond based on capabilities
        - Can dynamically discover and collaborate with other agents as needed
        - Maintains its own internal state and conversation tracking
        - Operates without central coordination or control

        The agent can leverage its internal workflow (which may include its own multi-agent system)
        to generate appropriate responses and handle complex tasks that may require collaboration
        with other independent agents in the decentralized network.
        """
        # Check if this is a collaboration request before calling super().process_message
        is_collaboration_request = (
            message.message_type == MessageType.REQUEST_COLLABORATION
        )

        # Call the superclass method to handle common message processing logic
        response = await super().process_message(message)
        if response:
            logger.info(
                f"AI Agent {self.agent_id} returning response from super().process_message: {response.content[:50]}..."
            )
            return response

        try:
            # Initialize workflow if it wasn't initialized in the constructor
            if self.workflow is None:
                if (
                    hasattr(self, "_hub")
                    and self._hub is not None
                    and hasattr(self, "_registry")
                    and self._registry is not None
                ):
                    logger.info(
                        f"AI Agent {self.agent_id}: Initializing workflow on first message"
                    )
                    self.workflow = self._initialize_workflow()
                else:
                    logger.error(
                        f"AI Agent {self.agent_id}: Cannot initialize workflow, registry or hub not set"
                    )

                    error_msg = "I'm sorry, I'm not fully initialized yet. Please try again later."
                    error_type = "initialization_error"

                    # Use COLLABORATION_RESPONSE for collaboration requests
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
                            "error_type": error_type,
                            **(
                                {"original_message_type": "ERROR"}
                                if is_collaboration_request
                                else {}
                            ),
                        },
                    )

            # If workflow is still None, return an error
            if self.workflow is None:
                logger.error(
                    f"AI Agent {self.agent_id}: Cannot process message, workflow not initialized"
                )

                error_msg = (
                    "I'm sorry, I'm not fully initialized yet. Please try again later."
                )
                error_type = "initialization_error"

                # Use COLLABORATION_RESPONSE for collaboration requests
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
                        "error_type": error_type,
                        **(
                            {"original_message_type": "ERROR"}
                            if is_collaboration_request
                            else {}
                        ),
                    },
                )

            # Check if this is an error message that needs special handling
            if message.message_type == MessageType.ERROR:
                logger.warning(
                    f"AI Agent {self.agent_id} received error message: {message.content[:100]}..."
                )

                # If this is from a collaboration, we should handle it gracefully
                if "error_type" in message.metadata:
                    error_type = message.metadata["error_type"]

                    # Find the original human in the conversation chain
                    human_sender = await self._find_human_in_conversation_chain(
                        message.sender_id
                    )

                    if human_sender and error_type in [
                        "timeout",
                        "max_retries_exceeded",
                        "collaboration_failed",
                    ]:
                        # Create a helpful response to the human explaining the issue
                        error_explanation = f"I encountered an issue while working with {message.sender_id}: {message.content}\n\n"
                        error_explanation += "I'll try to answer your question with the information I have available."

                        # Create a response message to the human
                        return Message.create(
                            sender_id=self.agent_id,
                            receiver_id=human_sender,
                            content=error_explanation,
                            sender_identity=self.identity,
                            message_type=MessageType.TEXT,
                            metadata={"handled_error": error_type},
                        )

            # Special handling for collaboration requests
            # This ensures responses are properly correlated with the original request

            # Get the conversation ID for this sender
            conversation_id = self._get_conversation_id(message.sender_id)

            # Get the callback manager from interaction_control
            # Only include our rate limiting callback, not a tracer
            callbacks = self.interaction_control.get_callback_manager()

            # Set up the configuration with the thread ID for memory persistence and callbacks
            # Use the thread_id for LangGraph memory persistence
            config = {
                "configurable": {
                    "thread_id": conversation_id,
                    # Add a run name for better LangSmith organization
                    "run_name": f"Agent {self.agent_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                },
                "callbacks": callbacks,
            }

            # Ensure the prompt_tools has the correct agent_id set
            if (
                self._prompt_tools
                and self._prompt_tools._current_agent_id != self.agent_id
            ):
                self._prompt_tools.set_current_agent(self.agent_id)
                logger.debug(
                    f"AI Agent {self.agent_id}: Reset current agent ID in tools before workflow invocation"
                )

            # Create the initial state for the workflow
            initial_state = {
                "messages": [HumanMessage(content=message.content)],
                "sender": message.sender_id,
                "receiver": self.agent_id,
                "message_type": message.message_type,
                "metadata": message.metadata or {},
                "max_retries": 2,  # Set a maximum number of retries for collaboration
                "retry_count": 0,  # Initialize retry count
            }
            logger.debug(
                f"AI Agent {self.agent_id} invoking workflow with conversation ID: {conversation_id}"
            )

            # Use the provided runnable with a timeout
            try:
                # Invoke the workflow with a timeout and callbacks
                response = await asyncio.wait_for(
                    self.workflow.ainvoke(initial_state, config),
                    timeout=180.0,  # 3 minute timeout for workflow execution
                )
                logger.debug(f"AI Agent {self.agent_id} workflow invocation complete.")
            except asyncio.TimeoutError:
                logger.error(f"AI Agent {self.agent_id} workflow execution timed out")

                # Create a timeout response
                timeout_message = "I'm sorry, but this request is taking too long to process. Please try again with a simpler request or break it down into smaller parts."

                # Use COLLABORATION_RESPONSE for collaboration requests
                message_type = (
                    MessageType.COLLABORATION_RESPONSE
                    if is_collaboration_request
                    else MessageType.ERROR
                )

                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content=timeout_message,
                    sender_identity=self.identity,
                    message_type=message_type,
                    metadata={
                        "error_type": "workflow_timeout",
                        **(
                            {"original_message_type": "ERROR"}
                            if is_collaboration_request
                            else {}
                        ),
                    },
                )

            # Extract the last message from the workflow response
            last_message = response["messages"][-1]
            logger.debug(
                f"AI Agent {self.agent_id} extracted last message from workflow response."
            )

            # Token counting and rate limiting
            total_tokens = 0
            if hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
                total_tokens = last_message.usage_metadata.get("total_tokens", 0)
            logger.debug(f"AI Agent {self.agent_id} token count: {total_tokens}")

            # Update token count after response - this will automatically trigger cooldown if needed
            # through the callback we set earlier
            state = await self.interaction_control.process_interaction(
                token_count=total_tokens, conversation_id=conversation_id
            )

            # Handle different interaction states
            if state == InteractionState.STOP:
                logger.info(
                    f"AI Agent {self.agent_id} reached maximum turns with {message.sender_id}. Ending conversation."
                )
                # End the conversation
                self.end_conversation(message.sender_id)
                last_message.content = f"{last_message.content}\n\nWe've reached the maximum number of turns for this conversation. If you need further assistance, please start a new conversation."

            elif state == InteractionState.WAIT:
                logger.info(
                    f"AI Agent {self.agent_id} is in cooldown state with {message.sender_id}."
                )
                # We don't need to create a special message here as the cooldown callback
                # will have already set the agent's cooldown state, which will be handled
                # by the BaseAgent.process_message method on the next interaction

            # Update conversation tracking
            if message.sender_id in self.active_conversations:
                self.active_conversations[message.sender_id]["message_count"] += 1
                self.active_conversations[message.sender_id][
                    "last_message_time"
                ] = datetime.now()
                logger.debug(
                    f"AI Agent {self.agent_id} updated active conversation with {message.sender_id}."
                )
            else:
                self.active_conversations[message.sender_id] = {
                    "message_count": 1,
                    "last_message_time": datetime.now(),
                }
                logger.debug(
                    f"AI Agent {self.agent_id} created new active conversation with {message.sender_id}."
                )

            # Determine the appropriate message type for the response
            # Always use COLLABORATION_RESPONSE for collaboration requests
            response_message_type = (
                MessageType.COLLABORATION_RESPONSE
                if is_collaboration_request
                else MessageType.RESPONSE
            )
            if is_collaboration_request:
                logger.info(
                    f"AI Agent {self.agent_id} sending collaboration response to {message.sender_id}"
                )

            # Create response metadata
            response_metadata = {
                "token_count": total_tokens,
            }

            # Add response_to if this is a response to a request with an ID
            if message.metadata and "request_id" in message.metadata:
                response_metadata["response_to"] = message.metadata["request_id"]
                logger.debug(
                    f"AI Agent {self.agent_id} adding response correlation: {message.metadata['request_id']}"
                )
            elif (
                hasattr(self, "pending_requests")
                and message.sender_id in self.pending_requests
            ):
                # If we don't have a request_id in the message metadata, but we have one stored in pending_requests,
                # use that one instead
                request_id = self.pending_requests[message.sender_id].get("request_id")
                if request_id:
                    response_metadata["response_to"] = request_id
                    logger.debug(
                        f"AI Agent {self.agent_id} adding response correlation from pending_requests: {request_id}"
                    )

            # Create the response message
            response_message = Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=last_message.content,
                sender_identity=self.identity,
                message_type=response_message_type,
                metadata=response_metadata,
            )
            logger.info(
                f"AI Agent {self.agent_id} sending response to {message.sender_id}: {response_message.content[:50]}..."
            )
            return response_message

        except Exception as e:
            logger.exception(
                f"AI Agent {self.agent_id} error processing message: {str(e)}"
            )

            # Create an error response
            # Use COLLABORATION_RESPONSE for collaboration requests
            message_type = (
                MessageType.COLLABORATION_RESPONSE
                if is_collaboration_request
                else MessageType.ERROR
            )

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"I encountered an unexpected error while processing your request: {str(e)}\n\nPlease try again with a different approach.",
                sender_identity=self.identity,
                message_type=message_type,
                metadata={
                    "error_type": "processing_error",
                    **(
                        {"original_message_type": "ERROR"}
                        if is_collaboration_request
                        else {}
                    ),
                },
            )

    # Property for prompt_tools to ensure consistent access
    @property
    def prompt_tools(self):
        """Get the prompt_tools property."""
        return self._prompt_tools

    @prompt_tools.setter
    def prompt_tools(self, value):
        """Set the prompt_tools property."""
        self._prompt_tools = value

    def set_cooldown(self, duration: int) -> None:
        """Set a cooldown period for the agent.

        Args:
            duration: Cooldown duration in seconds
        """
        # Call the parent class method to set the cooldown
        super().set_cooldown(duration)

        # Log detailed information about the cooldown
        logger.warning(
            f"AI Agent {self.agent_id} entered cooldown for {duration} seconds due to rate limiting."
        )

        # If this is a UI agent, we might want to send a notification to the UI
        if self.is_ui_mode:
            # TODO: This would be implemented by a UI notification system
            logger.info(
                f"UI notification: Agent {self.agent_id} is in cooldown for {duration} seconds."
            )

    def reset_interaction_state(self) -> None:
        """Reset the interaction state of the agent.

        This resets both the cooldown state and the turn counter.
        """
        # Reset the cooldown state
        self.reset_cooldown()

        # Reset the turn counter in the interaction control
        if hasattr(self, "interaction_control"):
            self.interaction_control.reset_turn_counter()
            logger.info(f"AI Agent {self.agent_id} interaction state reset.")

        # Log conversation statistics
        if hasattr(self, "interaction_control") and hasattr(
            self.interaction_control, "get_conversation_stats"
        ):
            stats = self.interaction_control.get_conversation_stats()
            if stats:
                logger.info(
                    f"AI Agent {self.agent_id} conversation statistics: {len(stats)} conversations tracked."
                )
                for conv_id, conv_stats in stats.items():
                    logger.info(
                        f"Conversation {conv_id}: {conv_stats['total_tokens']} tokens, {conv_stats['turn_count']} turns"
                    )
