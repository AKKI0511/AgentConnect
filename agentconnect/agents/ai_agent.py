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
from typing import List, Optional, Union, Dict, Any
from pathlib import Path

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import BaseTool

# Absolute imports from agentconnect package
from agentconnect.core.agent import BaseAgent
from agentconnect.core.message import Message
from agentconnect.core.payment_constants import POC_PAYMENT_TOKEN_SYMBOL
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
from agentconnect.utils.payment_helper import validate_cdp_environment

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
        custom_tools: Optional[List[BaseTool]] = None,
        agent_type: str = "ai",
        enable_payments: bool = False,
        verbose: bool = False,
        wallet_data_dir: Optional[Union[str, Path]] = None,
        external_callbacks: Optional[List[BaseCallbackHandler]] = None,
        model_config: Optional[Dict[str, Any]] = None,
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
            enable_payments: Whether to enable payment capabilities
            verbose: Whether to enable verbose logging
            wallet_data_dir: Optional custom directory for wallet data storage
            external_callbacks: Optional list of external callback handlers to include
            model_config: Optional dict of default model parameters (e.g., temperature, max_tokens)
        """
        # Validate CDP environment if payments are requested
        actual_enable_payments = enable_payments
        if enable_payments:
            is_valid, message = validate_cdp_environment()
            if not is_valid:
                logger.warning(
                    f"Payment capabilities requested for agent {agent_id} but environment validation failed: {message}"
                )
                logger.warning(
                    f"Payment capabilities will be disabled for agent {agent_id}"
                )
                actual_enable_payments = False
            else:
                logger.info(
                    f"CDP environment validation passed for agent {agent_id}: {message}"
                )

        # Store the model config before initializing LLM
        self.model_config = model_config or {}

        # Initialize base agent
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.AI,
            identity=identity,
            capabilities=capabilities or [],
            organization_id=organization_id,
            interaction_modes=interaction_modes,
            enable_payments=actual_enable_payments,
            wallet_data_dir=wallet_data_dir,
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
        self.verbose = verbose
        self.custom_tools = custom_tools or []
        self._prompt_tools = prompt_tools
        self.external_callbacks = external_callbacks or []
        self.prompt_templates = prompt_templates or PromptTemplates()
        self.workflow = None

        # Initialize hub and registry references
        self._hub = None
        self._registry = None

        # Initialize token tracking and rate limiting
        token_config = TokenConfig(
            max_tokens_per_minute=max_tokens_per_minute,
            max_tokens_per_hour=max_tokens_per_hour,
        )

        self.interaction_control = InteractionControl(
            agent_id=self.agent_id, token_config=token_config, max_turns=max_turns
        )
        self.interaction_control.set_cooldown_callback(self.set_cooldown)

        # Initialize the LLM
        self.llm = self._initialize_llm()
        logger.debug(f"Initialized LLM for AI Agent {self.agent_id}: {self.llm}")
        logger.info(
            f"AI Agent {self.agent_id} initialized with {len(self.capabilities)} capabilities"
        )

    @property
    def hub(self):
        """Get the hub property."""
        return self._hub

    @hub.setter
    def hub(self, value):
        """Set the hub property."""
        self._hub = value
        self._initialize_workflow_if_ready()

    @property
    def registry(self):
        """Get the registry property."""
        return self._registry

    @registry.setter
    def registry(self, value):
        """Set the registry property."""
        self._registry = value
        self._initialize_workflow_if_ready()

    @property
    def prompt_tools(self):
        """Get the prompt_tools property."""
        return self._prompt_tools

    @prompt_tools.setter
    def prompt_tools(self, value):
        """Set the prompt_tools property."""
        self._prompt_tools = value

    def _initialize_workflow_if_ready(self):
        """Initialize the workflow if both registry and hub are set."""
        if (
            hasattr(self, "_hub")
            and self._hub is not None
            and hasattr(self, "_registry")
            and self._registry is not None
            and self.workflow is None
        ):
            logger.debug(
                f"AI Agent {self.agent_id}: Registry and hub are set, initializing workflow"
            )
            self.workflow = self._initialize_workflow()
            logger.debug(f"AI Agent {self.agent_id}: Workflow initialized")

    def _initialize_llm(self):
        """Initialize the LLM based on the provider type and model name."""
        from agentconnect.providers import ProviderFactory

        provider = ProviderFactory.create_provider(self.provider_type, self.api_key)
        logger.debug(f"AI Agent {self.agent_id}: LLM provider created: {provider}")
        return provider.get_langchain_llm(
            model_name=self.model_name, **self.model_config or {}
        )

    def _initialize_workflow(self) -> Runnable:
        """Initialize the workflow for the agent."""
        # Determine if we're in standalone mode
        is_standalone = (
            not hasattr(self, "_registry")
            or self._registry is None
            or not hasattr(self, "_hub")
            or self._hub is None
        )

        # Create a PromptTools instance if not already provided
        if self._prompt_tools is None:
            self._prompt_tools = PromptTools(
                agent_registry=self._registry, communication_hub=self._hub, llm=self.llm
            )
            logger.debug(
                f"AI Agent {self.agent_id}: Created {'standalone' if is_standalone else 'connected'} PromptTools instance."
            )

        # Set the current agent context for the tools
        self._prompt_tools.set_current_agent(self.agent_id)

        # Create system config if not already created
        if not hasattr(self, "system_config"):
            # Add standalone mode note to system config if in standalone mode
            additional_context = {}
            if is_standalone:
                additional_context["standalone_mode"] = (
                    "You are operating in standalone mode without connections to other agents. "
                    "Focus on using your internal capabilities to help the user directly. "
                    "If collaboration would normally be useful, explain why it's not available "
                    "and offer the best alternative solutions you can provide on your own."
                )

            self.system_config = SystemPromptConfig(
                name=self.name,
                capabilities=self.capabilities,
                personality=self.personality,
                additional_context=additional_context,
            )

        # Initialize custom tools list
        custom_tools_list = list(self.custom_tools) if self.custom_tools else []

        # Add payment tools if enabled
        if self.enable_payments and self.agent_kit is not None:
            try:
                from coinbase_agentkit_langchain import get_langchain_tools

                agentkit_tools = get_langchain_tools(self.agent_kit)
                custom_tools_list.extend(agentkit_tools)

                tool_names = [tool.name for tool in agentkit_tools]
                logger.info(
                    f"AI Agent {self.agent_id}: Added {len(agentkit_tools)} AgentKit payment tools: {tool_names}"
                )
                payment_tool = (
                    "native_transfer"
                    if POC_PAYMENT_TOKEN_SYMBOL == "ETH"
                    else "erc20_transfer"
                )
                logger.info(
                    f"AI Agent {self.agent_id}: Will use {payment_tool} for payments with {POC_PAYMENT_TOKEN_SYMBOL} token"
                )

                # Enable payment capabilities in the system prompt config
                self.system_config.enable_payments = True
                self.system_config.payment_token_symbol = POC_PAYMENT_TOKEN_SYMBOL
                logger.info(
                    f"AI Agent {self.agent_id}: Enabled payment capabilities in system prompt"
                )
            except ImportError as e:
                logger.warning(
                    f"AI Agent {self.agent_id}: Could not import AgentKit LangChain tools: {e}"
                )
                logger.warning(
                    "To use payment capabilities, install with: pip install coinbase-agentkit-langchain"
                )
            except Exception as e:
                logger.error(
                    f"AI Agent {self.agent_id}: Error initializing AgentKit tools: {e}"
                )

        # Create the workflow with all components
        workflow = create_workflow_for_agent(
            agent_type=self.workflow_agent_type,
            system_config=self.system_config,
            llm=self.llm,
            tools=self._prompt_tools,
            prompt_templates=self.prompt_templates,
            agent_id=self.agent_id,
            custom_tools=custom_tools_list,
            verbose=self.verbose,
        )

        return workflow.compile()

    def _create_error_response(
        self,
        message: Message,
        error_msg: str,
        error_type: str,
        is_collaboration_request: bool = False,
    ) -> Message:
        """Create a standardized error response message."""
        message_type = (
            MessageType.COLLABORATION_RESPONSE
            if is_collaboration_request
            else MessageType.ERROR
        )

        metadata = {"error_type": error_type}
        if is_collaboration_request:
            metadata["original_message_type"] = "ERROR"

        return Message.create(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            content=error_msg,
            sender_identity=self.identity,
            message_type=message_type,
            metadata=metadata,
        )

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
        # Check if this is a collaboration request
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
            # Initialize workflow if needed
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
                    return self._create_error_response(
                        message,
                        "I'm sorry, I'm not fully initialized yet. Please try again later.",
                        "initialization_error",
                        is_collaboration_request,
                    )

            # If workflow is still None, return an error
            if self.workflow is None:
                logger.error(
                    f"AI Agent {self.agent_id}: Cannot process message, workflow not initialized"
                )
                return self._create_error_response(
                    message,
                    "I'm sorry, I'm not fully initialized yet. Please try again later.",
                    "initialization_error",
                    is_collaboration_request,
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

            # Get the conversation ID for this sender
            conversation_id = self._get_conversation_id(message.sender_id)

            # Setup callbacks - combine rate limiting callbacks with any external ones
            callbacks = self.interaction_control.get_callback_handlers()
            if self.external_callbacks:
                callbacks.extend(self.external_callbacks)

            # Ensure the prompt_tools has the correct agent_id set
            if (
                self._prompt_tools
                and self._prompt_tools._current_agent_id != self.agent_id
            ):
                self._prompt_tools.set_current_agent(self.agent_id)

            # Add context prefix based on sender/message type
            sender_type = (
                "Human" if message.sender_id.startswith("human") else "AI Agent"
            )
            is_collab_request = (
                message.message_type == MessageType.REQUEST_COLLABORATION
            )
            is_collab_response = "response_to" in (message.metadata or {})

            context_prefix = ""
            if sender_type == "AI Agent":
                if is_collab_request:
                    context_prefix = f"[Incoming Collaboration Request from AI Agent {message.sender_id}]:\n"
                elif is_collab_response:
                    context_prefix = f"[Incoming Response from Collaborating AI Agent {message.sender_id}]:\n"
                else:
                    context_prefix = (
                        f"[Incoming Message from AI Agent {message.sender_id}]:\n"
                    )

            workflow_input_content = f"{context_prefix}{message.content}"

            # Create the initial state and config for the workflow
            initial_state = {
                "messages": [HumanMessage(content=workflow_input_content)],
                "sender": message.sender_id,
                "receiver": self.agent_id,
                "message_type": message.message_type,
                "metadata": message.metadata or {},
                "max_retries": 2,
                "retry_count": 0,
            }

            config = {
                "configurable": {
                    "thread_id": conversation_id,
                    "run_name": f"Agent {self.agent_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                },
                "callbacks": callbacks,
            }

            logger.debug(
                f"AI Agent {self.agent_id} invoking workflow with conversation ID: {conversation_id}"
            )

            # Invoke the workflow with a timeout
            try:
                response_state = await asyncio.wait_for(
                    self.workflow.ainvoke(initial_state, config),
                    timeout=180.0,  # 3 minute timeout
                )
                logger.debug(f"AI Agent {self.agent_id} workflow invocation complete.")
            except asyncio.TimeoutError:
                logger.error(f"AI Agent {self.agent_id} workflow execution timed out")
                return self._create_error_response(
                    message,
                    "I'm sorry, but this request is taking too long to process. Please try again with a simpler request or break it down into smaller parts.",
                    "workflow_timeout",
                    is_collaboration_request,
                )

            # Extract the last message from the workflow response state
            if "messages" not in response_state or not response_state["messages"]:
                logger.error(
                    f"AI Agent {self.agent_id}: Workflow returned empty or invalid messages state."
                )
                return self._create_error_response(
                    message,
                    "Internal error: Could not retrieve response.",
                    "empty_workflow_response",
                    is_collaboration_request,
                )

            last_message = response_state["messages"][-1]

            # Token counting and rate limiting
            total_tokens = 0
            if hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
                total_tokens = last_message.usage_metadata.get("total_tokens", 0)

            # Update token count and handle rate limiting
            state = await self.interaction_control.process_interaction(
                token_count=total_tokens, conversation_id=conversation_id
            )

            # Handle different interaction states
            if state == InteractionState.STOP:
                logger.info(
                    f"AI Agent {self.agent_id} reached maximum turns with {message.sender_id}. Ending conversation."
                )
                self.end_conversation(message.sender_id)
                last_message.content = f"{last_message.content}\n\nWe've reached the maximum number of turns for this conversation. If you need further assistance, please start a new conversation."

            # Update conversation tracking
            current_time = datetime.now()
            if message.sender_id in self.active_conversations:
                self.active_conversations[message.sender_id]["message_count"] += 1
                self.active_conversations[message.sender_id][
                    "last_message_time"
                ] = current_time
            else:
                self.active_conversations[message.sender_id] = {
                    "message_count": 1,
                    "last_message_time": current_time,
                }

            # Determine the appropriate message type for the response
            response_message_type = (
                MessageType.COLLABORATION_RESPONSE
                if is_collaboration_request
                else MessageType.RESPONSE
            )

            # Create response metadata
            response_metadata = {"token_count": total_tokens}

            # Add response_to if this is a response to a request with an ID
            if message.metadata and "request_id" in message.metadata:
                response_metadata["response_to"] = message.metadata["request_id"]
            elif (
                hasattr(self, "pending_requests")
                and message.sender_id in self.pending_requests
            ):
                request_id = self.pending_requests[message.sender_id].get("request_id")
                if request_id:
                    response_metadata["response_to"] = request_id

            # Create and return the response message
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
            return self._create_error_response(
                message,
                f"I encountered an unexpected error while processing your request: {str(e)}\n\nPlease try again with a different approach.",
                "processing_error",
                is_collaboration_request,
            )

    def set_cooldown(self, duration: int) -> None:
        """Set a cooldown period for the agent."""
        # Call the parent class method to set the cooldown
        super().set_cooldown(duration)
        logger.warning(
            f"AI Agent {self.agent_id} entered cooldown for {duration} seconds due to rate limiting."
        )

        # UI notification if in UI mode
        if self.is_ui_mode:
            # TODO: This would be implemented by a UI notification system
            logger.info(
                f"UI notification: Agent {self.agent_id} is in cooldown for {duration} seconds."
            )

    def reset_interaction_state(self) -> None:
        """
        Reset the interaction state of the agent. This resets both the cooldown state and the turn counter.
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

    async def chat(
        self,
        query: str,
        conversation_id: str = "standalone_chat",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Allows direct interaction with the agent without needing a CommunicationHub or AgentRegistry.

        This method is useful for testing or using a single agent instance directly.
        It simulates a user query and returns the agent's response, maintaining
        conversation history based on the conversation_id if memory is configured.

        Args:
            query: The user's input/query to the agent.
            conversation_id: An identifier for the conversation thread. Defaults to "standalone_chat".
                             Use different IDs to maintain separate conversation histories.
            metadata: Optional metadata to pass to the workflow.

        Returns:
            The agent's response as a string.

        Raises:
            RuntimeError: If the workflow cannot be initialized or fails unexpectedly.
            asyncio.TimeoutError: If the workflow execution times out.
        """
        logger.info(
            f"AI Agent {self.agent_id} received direct chat query: {query[:50]}..."
        )

        # Initialize workflow if not already done
        if self.workflow is None:
            try:
                # Ensure hub and registry attributes exist (as None) for standalone mode
                if not hasattr(self, "_registry"):
                    self._registry = None
                if not hasattr(self, "_hub"):
                    self._hub = None

                # Create PromptTools if needed for standalone mode
                if not hasattr(self, "_prompt_tools") or self._prompt_tools is None:
                    self._prompt_tools = PromptTools(
                        agent_registry=None,
                        communication_hub=None,
                        llm=self._initialize_llm(),
                    )
                    logger.info(
                        f"AI Agent {self.agent_id}: Created standalone PromptTools instance."
                    )

                # Set current agent context
                self._prompt_tools.set_current_agent(self.agent_id)

                # Create standalone system config
                self.system_config = SystemPromptConfig(
                    name=self.name,
                    capabilities=self.capabilities,
                    personality=self.personality,
                    additional_context={
                        "standalone_mode": (
                            "You are operating in standalone mode without connections to other agents. "
                            "Focus on using your internal capabilities to help the user directly. "
                            "If collaboration would normally be useful, explain why it's not available "
                            "and offer the best alternative solutions you can provide on your own."
                        )
                    },
                )

                # Initialize workflow
                self.workflow = self._initialize_workflow()
                if self.workflow is None:
                    raise RuntimeError("Workflow initialization failed.")

                logger.info(
                    f"AI Agent {self.agent_id}: Workflow initialized for standalone chat."
                )
            except Exception as e:
                logger.exception(
                    f"AI Agent {self.agent_id}: Failed to initialize workflow for chat: {e}"
                )
                raise RuntimeError(f"Failed to initialize agent workflow: {e}") from e

        # Set up workflow input and configuration
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "sender": "user_standalone",
            "receiver": self.agent_id,
            "message_type": MessageType.TEXT,
            "metadata": metadata or {},
            "max_retries": 0,
            "retry_count": 0,
        }

        # Prepare callbacks
        callbacks = self.interaction_control.get_callback_handlers()
        if self.external_callbacks:
            callbacks.extend(self.external_callbacks)

        # Create workflow configuration
        config = {
            "configurable": {
                "thread_id": conversation_id,
                "run_name": f"Agent {self.agent_id} - Standalone Chat - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            },
            "callbacks": callbacks,
        }

        # Ensure prompt_tools has current agent context
        if (
            hasattr(self, "_prompt_tools")
            and self._prompt_tools
            and self._prompt_tools._current_agent_id != self.agent_id
        ):
            self._prompt_tools.set_current_agent(self.agent_id)

        # Invoke workflow
        try:
            logger.debug(
                f"AI Agent {self.agent_id} invoking workflow for chat with conversation ID: {conversation_id}"
            )
            response_state = await asyncio.wait_for(
                self.workflow.ainvoke(initial_state, config),
                timeout=180.0,
            )
            logger.debug(
                f"AI Agent {self.agent_id}: Chat workflow invocation complete."
            )
        except asyncio.TimeoutError as e:
            logger.error(
                f"AI Agent {self.agent_id}: Chat workflow execution timed out."
            )
            raise e
        except Exception as e:
            logger.exception(
                f"AI Agent {self.agent_id}: Error during chat workflow invocation: {e}"
            )
            raise RuntimeError(f"Agent workflow failed during chat: {e}") from e

        # Extract response
        if "messages" not in response_state or not response_state["messages"]:
            logger.error(
                f"AI Agent {self.agent_id}: Chat workflow returned empty or invalid messages state."
            )
            raise RuntimeError("Agent workflow returned no response message.")

        # Get response content
        last_message = response_state["messages"][-1]
        if hasattr(last_message, "content"):
            response_content = last_message.content
        else:
            logger.error(
                f"AI Agent {self.agent_id}: Last message in chat response has no content: {last_message}"
            )
            raise RuntimeError("Agent workflow returned unexpected message format.")

        # Handle token tracking and rate limiting
        total_tokens = 0
        if hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
            total_tokens = last_message.usage_metadata.get("total_tokens", 0)

        await self.interaction_control.process_interaction(
            token_count=total_tokens, conversation_id=conversation_id
        )

        logger.info(
            f"AI Agent {self.agent_id} generated chat response: {response_content[:50]}..."
        )
        return response_content
