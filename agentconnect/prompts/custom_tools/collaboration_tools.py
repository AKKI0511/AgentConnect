"""
Collaboration tools for agent workflows.

This module provides tools for agent search and collaboration within the AgentConnect framework.
These tools help agents find other specialized agents and collaborate on tasks.
"""

import asyncio
import logging
import uuid
import json
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.types import AgentType

logger = logging.getLogger(__name__)

# Type variables for better type hinting
T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


# --- Input/Output schemas for tools ---


class AgentSearchInput(BaseModel):
    """Input schema for agent search."""

    capability_name: str = Field(
        description="The specific skill or capability required for the task (e.g., 'general_research', 'telegram_broadcast', 'image_generation'). Be descriptive but concise."
    )
    limit: int = Field(
        10, description="Maximum number of matching agents to return (default 10)."
    )
    similarity_threshold: float = Field(
        0.2,
        description="How closely the agent's capability must match your query (0.0=broad match, 1.0=exact match, default 0.2). Use higher values for very specific needs.",
    )


class AgentSearchOutput(BaseModel):
    """Output schema for agent search."""

    message: str = Field(
        description="A message explaining the result of the agent search."
    )
    agent_ids: List[str] = Field(
        description="A list of unique IDs for agents possessing the required capability."
    )
    capabilities: List[Dict[str, Any]] = Field(
        description="A list of dictionaries, each containing details for a found agent: their `agent_id`, their full list of capabilities, and their `payment_address` (if applicable)."
    )

    def __str__(self) -> str:
        """Return a clean JSON string representation."""
        return self.model_dump_json(indent=2)


class SendCollaborationRequestInput(BaseModel):
    """Input schema for sending a collaboration request."""

    target_agent_id: str = Field(
        description="The exact `agent_id` (obtained from `search_for_agents` output) of the agent you want to delegate the task to."
    )
    task: str = Field(
        description="A clear and detailed description of the task, providing ALL necessary context for the collaborating agent to understand and execute the request."
    )
    timeout: int = Field(
        default=120,
        description="Maximum seconds to wait for the collaborating agent's response (default 120).",
    )

    class Config:
        """Config for the SendCollaborationRequestInput."""

        extra = "allow"  # Allow additional fields to be passed as kwargs


class SendCollaborationRequestOutput(BaseModel):
    """Output schema for sending a collaboration request."""

    success: bool = Field(
        description="Indicates if the request was successfully SENT (True/False). Does NOT guarantee the collaborator completed the task."
    )
    response: Optional[str] = Field(
        None,
        description="The direct message content received back from the collaborating agent. Analyze this response carefully to determine the next step (e.g., pay, provide more info, present to user).",
    )
    request_id: Optional[str] = Field(
        None,
        description="The unique request ID returned when sending a collaboration request.",
    )
    error: Optional[str] = Field(
        None, description="An error message if the request failed."
    )

    def __str__(self) -> str:
        """Return a clean JSON string representation."""
        return self.model_dump_json(indent=2)


class CheckCollaborationResultInput(BaseModel):
    """Input schema for checking collaboration results."""

    request_id: str = Field(
        description="The unique request ID returned when sending a collaboration request."
    )


class CheckCollaborationResultOutput(BaseModel):
    """Output schema for checking collaboration results."""

    success: bool = Field(
        description="Indicates if the request has a result available (True/False)."
    )
    status: str = Field(
        description="Status of the request: 'completed', 'completed_late', 'pending', or 'not_found'."
    )
    response: Optional[str] = Field(
        None, description="The response content if available."
    )

    def __str__(self) -> str:
        """Return a clean JSON string representation."""
        return self.model_dump_json(indent=2)


# --- Implementation of connected and standalone tools ---


def create_agent_search_tool(
    agent_registry: Optional[AgentRegistry] = None,
    current_agent_id: Optional[str] = None,
    communication_hub: Optional[CommunicationHub] = None,
) -> StructuredTool:
    """
    Create a tool for searching agents by capability.

    Args:
        agent_registry: Registry for accessing agent information
        current_agent_id: ID of the agent currently using the tool
        communication_hub: Hub for agent communication

    Returns:
        A StructuredTool for agent search that can be used in agent workflows
    """
    # Determine if we're in standalone mode
    standalone_mode = agent_registry is None or communication_hub is None

    # Common description for the tool
    base_description = "Finds other agents within the network that possess specific capabilities you lack, enabling task delegation."

    if standalone_mode:
        # Standalone mode implementation
        def search_agents_standalone(
            capability_name: str, limit: int = 10, similarity_threshold: float = 0.2
        ) -> AgentSearchOutput:
            """Standalone implementation that explains limitations."""
            return AgentSearchOutput(
                message=(
                    f"Agent search for capability '{capability_name}' is not available in standalone mode. "
                    "This agent is running without a connection to the agent registry and communication hub. "
                    "Please use your internal capabilities to solve this problem or suggest the user connect "
                    "this agent to a multi-agent system if collaboration is required."
                ),
                agent_ids=[],
                capabilities=[],
            )

        description = f"[STANDALONE MODE] {base_description} Note: In standalone mode, this tool will explain why agent search isn't available."

        tool = StructuredTool.from_function(
            func=search_agents_standalone,
            name="search_for_agents",
            description=description,
            args_schema=AgentSearchInput,
            return_direct=False,
            metadata={"category": "collaboration"},
        )
        return tool

    # Connected mode implementation
    async def search_agents_async(
        capability_name: str, limit: int = 10, similarity_threshold: float = 0.2
    ) -> AgentSearchOutput:
        """
        Search for agents with a specific capability.

        This function implements a comprehensive filtering strategy to avoid redundant
        or inappropriate agent collaborations:

        1. The current agent itself (you can't collaborate with yourself)
        2. Any agents the current agent is already in active conversation with
        3. Any agents the current agent has pending requests with
        4. Any agents the current agent has recently communicated with
        5. Human agents (which aren't suitable for automated collaboration)

        This filtering is critical to prevent:
        - Redundant collaboration requests to the same agent
        - Parallel conversations with the same agent causing confusion
        - Circular collaboration chains
        - Message spamming through multiple channels to the same agent

        The function searches in three progressive steps:
        1. First tries semantic search for capability matching (most flexible)
        2. Falls back to exact capability name matching if no results
        3. Returns all available agents as a last resort

        Args:
            capability_name: The capability to search for
            limit: Maximum number of agents to return
            similarity_threshold: Minimum similarity score (0-1) required for results

        Returns:
            Dict containing agent_ids, capabilities, and optional message
        """
        logger.debug(f"Searching for agents with capability: {capability_name}")

        try:
            # Get agents to exclude (self + active conversations + pending requests)
            agents_to_exclude = []
            if current_agent_id:
                agents_to_exclude.append(current_agent_id)  # Exclude self

                # Get active conversations and pending requests if possible
                if communication_hub:
                    current_agent = await communication_hub.get_agent(current_agent_id)
                    if current_agent:
                        # Active conversations
                        if hasattr(current_agent, "active_conversations"):
                            agents_to_exclude.extend(
                                current_agent.active_conversations.keys()
                            )

                        # Pending requests
                        if hasattr(current_agent, "pending_requests"):
                            agents_to_exclude.extend(
                                current_agent.pending_requests.keys()
                            )

                        # Recent messages
                        if (
                            hasattr(current_agent, "message_history")
                            and current_agent.message_history
                        ):
                            recent_messages = (
                                current_agent.message_history[-10:]
                                if len(current_agent.message_history) > 10
                                else current_agent.message_history
                            )
                            for msg in recent_messages:
                                if (
                                    msg.sender_id != current_agent_id
                                    and msg.sender_id not in agents_to_exclude
                                ):
                                    agents_to_exclude.append(msg.sender_id)
                                if (
                                    msg.receiver_id != current_agent_id
                                    and msg.receiver_id not in agents_to_exclude
                                ):
                                    agents_to_exclude.append(msg.receiver_id)

            # Remove duplicates
            agents_to_exclude = list(set(agents_to_exclude))
            logger.debug(f"Excluding {len(agents_to_exclude)} agents from search")

            #########
            # Try semantic search first for better matching
            #########
            semantic_results = await agent_registry.get_by_capability_semantic(
                capability_name, limit=limit, similarity_threshold=similarity_threshold
            )

            if semantic_results:
                logger.debug(
                    f"Found {len(semantic_results)} agents via semantic search"
                )
                return format_agent_results(semantic_results, agents_to_exclude, limit)

            # Fall back to exact matching if semantic search returns no results
            exact_results = await agent_registry.get_by_capability(
                capability_name, limit=limit, similarity_threshold=similarity_threshold
            )

            if exact_results:
                logger.debug(f"Found {len(exact_results)} agents via exact matching")
                return format_exact_results(
                    exact_results, agents_to_exclude, capability_name, limit
                )

            # # As a last resort, get all agents
            # all_agents = await agent_registry.get_all_agents()
            # if all_agents:
            #     logger.debug(f"Returning all {len(all_agents)} agents as fallback")
            #     return format_exact_results(
            #         all_agents,
            #         agents_to_exclude,
            #         capability_name,
            #         limit,
            #         fallback_message=f"No specific agents for '{capability_name}'. Showing all available agents."
            #     )

            return AgentSearchOutput(
                agent_ids=[],
                capabilities=[],
                message=f"No agents found matching capability '{capability_name}'. Please try refining your search query with more specific capability terms.",
            )
        except Exception as e:
            logger.error(f"Error searching for agents: {str(e)}")
            return AgentSearchOutput(
                agent_ids=[],
                capabilities=[],
                message=f"Error searching for agents: {str(e)}",
            )

    def format_agent_results(
        semantic_results: List[Tuple[AgentRegistration, float]],
        agents_to_exclude: List[str],
        limit: int,
    ) -> AgentSearchOutput:
        """Format semantic search results."""
        agent_ids = []
        capabilities = []

        for agent, similarity in semantic_results:
            # Skip human agents and excluded agents
            if (
                agent.agent_type == AgentType.HUMAN
                or agent.agent_id in agents_to_exclude
            ):
                continue

            agent_ids.append(agent.agent_id)

            # Include all capabilities with similarity scores
            agent_capabilities = [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "similarity": round(float(similarity), 3),
                }
                for cap in agent.capabilities
            ]

            capabilities.append(
                {
                    "agent_id": agent.agent_id,
                    "capabilities": agent_capabilities,
                    **(
                        {"payment_address": agent.payment_address}
                        if agent.payment_address
                        else {}
                    ),
                }
            )

        return AgentSearchOutput(
            agent_ids=agent_ids[:limit],
            capabilities=capabilities[:limit],
            message="Review capabilities carefully before collaborating. Similarity scores under 0.5 may indicate limited relevance.",
        )

    def format_exact_results(
        results: List[AgentRegistration],
        agents_to_exclude: List[str],
        capability_name: str,
        limit: int,
        fallback_message: Optional[str] = None,
    ) -> AgentSearchOutput:
        """Format exact match or fallback results."""
        agent_ids = []
        capabilities = []

        for agent in results:
            # Skip human agents and excluded agents
            if (
                agent.agent_type == AgentType.HUMAN
                or agent.agent_id in agents_to_exclude
            ):
                continue

            agent_ids.append(agent.agent_id)

            # Calculate similarity for each capability
            agent_capabilities = [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "similarity": round(
                        float(
                            1.0 if cap.name.lower() == capability_name.lower() else 0.0
                        ),
                        3,
                    ),
                }
                for cap in agent.capabilities
            ]

            capabilities.append(
                {
                    "agent_id": agent.agent_id,
                    "capabilities": agent_capabilities,
                    **(
                        {"payment_address": agent.payment_address}
                        if agent.payment_address
                        else {}
                    ),
                }
            )

        message = (
            fallback_message or "Review capabilities carefully before collaborating."
        )
        return AgentSearchOutput(
            agent_ids=agent_ids[:limit],
            capabilities=capabilities[:limit],
            message=message,
        )

    # Synchronous wrapper
    def search_agents(
        capability_name: str, limit: int = 10, similarity_threshold: float = 0.2
    ) -> AgentSearchOutput:
        """Search for agents with a specific capability."""
        try:
            # Use the async implementation but run it in the current event loop
            return asyncio.run(
                search_agents_async(capability_name, limit, similarity_threshold)
            )
        except RuntimeError:
            # If we're already in an event loop, create a new one
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    search_agents_async(capability_name, limit, similarity_threshold)
                )
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in search_agents: {str(e)}")
            return AgentSearchOutput(
                message=f"Error in search_agents: {str(e)}",
                agent_ids=[],
                capabilities=[],
            )

    # Create a description that includes available capabilities if possible
    description = f"{base_description} Use this tool FIRST when you cannot handle a request directly. Returns a list of suitable agent IDs, their capabilities, and crucially, their `payment_address` if they accept payments for services."

    # Create and return the tool
    tool = StructuredTool.from_function(
        func=search_agents,
        name="search_for_agents",
        description=description,
        args_schema=AgentSearchInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=search_agents_async,
        metadata={"category": "collaboration"},
    )
    return tool


def create_send_collaboration_request_tool(
    communication_hub: Optional[CommunicationHub] = None,
    agent_registry: Optional[AgentRegistry] = None,
    current_agent_id: Optional[str] = None,
) -> StructuredTool:
    """
    Create a tool for sending collaboration requests to other agents.

    Args:
        communication_hub: Hub for agent communication
        agent_registry: Registry for accessing agent information
        current_agent_id: ID of the agent using the tool

    Returns:
        A StructuredTool for sending collaboration requests
    """
    # Determine if we're in standalone mode
    standalone_mode = (
        communication_hub is None or agent_registry is None or not current_agent_id
    )

    # Common description base
    base_description = (
        "Delegates a specific task to another agent identified by `search_for_agents`."
    )

    if standalone_mode:
        # Standalone mode implementation
        def send_request_standalone(
            target_agent_id: str, task: str, timeout: int = 30, **kwargs
        ) -> SendCollaborationRequestOutput:
            """Standalone implementation that explains limitations."""
            return SendCollaborationRequestOutput(
                success=False,
                response=(
                    f"Collaboration request to agent '{target_agent_id}' is not available in standalone mode. "
                    "This agent is running without a connection to other agents. "
                    "Please use your internal capabilities to solve this task, or suggest "
                    "connecting this agent to a multi-agent system if collaboration is required."
                ),
                request_id=None,
            )

        description = f"[STANDALONE MODE] {base_description} Note: In standalone mode, this tool will explain why collaboration isn't available."

        return StructuredTool.from_function(
            func=send_request_standalone,
            name="send_collaboration_request",
            description=description,
            args_schema=SendCollaborationRequestInput,
            return_direct=False,
            handle_tool_error=True,
            metadata={"category": "collaboration"},
        )

    # Connected mode implementation
    # Store the agent ID at creation time
    creator_agent_id = current_agent_id
    logger.debug(f"Creating collaboration request tool for agent: {creator_agent_id}")

    async def send_request_async(
        target_agent_id: str, task: str, timeout: int = 120, **kwargs
    ) -> SendCollaborationRequestOutput:
        """Send a collaboration request to another agent asynchronously."""
        sender_id = creator_agent_id

        # Validate request parameters
        if sender_id == target_agent_id:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Cannot send request to yourself.",
            )

        if not await communication_hub.is_agent_active(target_agent_id):
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Agent {target_agent_id} not found.",
            )

        if await agent_registry.get_agent_type(target_agent_id) == AgentType.HUMAN:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Cannot send requests to human agents.",
            )

        # Prepare collaboration metadata
        metadata = kwargs.copy() if kwargs else {}

        # Add collaboration chain tracking to prevent loops
        if "collaboration_chain" not in metadata:
            metadata["collaboration_chain"] = []

        if sender_id not in metadata["collaboration_chain"]:
            metadata["collaboration_chain"].append(sender_id)

        if target_agent_id in metadata["collaboration_chain"]:
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Detected loop in collaboration chain with {target_agent_id}.",
            )

        # If this is the first agent in the chain, store the original sender
        if len(metadata["collaboration_chain"]) == 1:
            metadata["original_sender"] = metadata["collaboration_chain"][0]

        # Prevent sending to original sender
        if (
            "original_sender" in metadata
            and metadata["original_sender"] == target_agent_id
        ):
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Cannot send request back to original sender {target_agent_id}.",
            )

        # Limit collaboration chain length
        if len(metadata["collaboration_chain"]) > 5:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Collaboration chain too long. Simplify request.",
            )

        try:
            # Calculate appropriate timeout
            adjusted_timeout = min(timeout or 120, 300)  # Cap at 5 minutes

            # Generate a unique request ID if not provided
            request_id = metadata.get("request_id", str(uuid.uuid4()))
            metadata["request_id"] = request_id

            # Send the request and wait for response
            logger.debug(f"Sending collaboration from {sender_id} to {target_agent_id}")
            response = await communication_hub.send_collaboration_request(
                sender_id=sender_id,
                receiver_id=target_agent_id,
                task_description=task,
                timeout=adjusted_timeout,
                **metadata,
            )

            # --- Handle potential non-string/list response from LLM --- START
            cleaned_response = response
            if not isinstance(response, str) and response is not None:
                if (
                    isinstance(response, list)
                    and len(response) == 1
                    and isinstance(response[0], str)
                ):
                    # Handle the specific case of ['string']
                    logger.warning(
                        f"Received list-wrapped response from {target_agent_id}, extracting string."
                    )
                    cleaned_response = response[0]
                else:
                    # For any other non-string type (dict, multi-list, int, etc.), convert to JSON string
                    try:
                        logger.warning(
                            f"Received non-string response type {type(response).__name__} from {target_agent_id}, converting to JSON string."
                        )
                        cleaned_response = json.dumps(
                            response
                        )  # Attempt JSON conversion
                    except TypeError as e:
                        # Fallback if JSON conversion fails (e.g., complex object)
                        logger.error(
                            f"Could not JSON serialize response type {type(response).__name__}: {e}. Using str() representation."
                        )
                        cleaned_response = str(response)
            # --- Handle potential non-string/list response from LLM --- END

            # Handle timeout case
            if cleaned_response is None or (
                isinstance(cleaned_response, str)
                and "No immediate response received" in cleaned_response
            ):
                logger.warning(f"Timeout on request to {target_agent_id}")
                return SendCollaborationRequestOutput(
                    success=False,
                    response=f"No immediate response from {target_agent_id} within {adjusted_timeout} seconds. "
                    f"The request is still processing (ID: {request_id}). "
                    f"Check for a late response using check_collaboration_result with this request ID.",
                    error="timeout",
                    request_id=request_id,
                )

            # Handle success case
            logger.debug(f"Got response from {target_agent_id}")
            return SendCollaborationRequestOutput(
                success=True, response=cleaned_response, request_id=request_id
            )

        except Exception as e:
            logger.exception(f"Error sending collaboration request: {str(e)}")
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Collaboration failed - {str(e)}",
                error="collaboration_exception",
            )

    # Synchronous wrapper
    def send_request(
        target_agent_id: str, task: str, timeout: int = 30, **kwargs
    ) -> SendCollaborationRequestOutput:
        """Send a collaboration request to another agent."""
        try:
            return asyncio.run(
                send_request_async(target_agent_id, task, timeout, **kwargs)
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    send_request_async(target_agent_id, task, timeout, **kwargs)
                )
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in send_request: {str(e)}")
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error sending collaboration request: {str(e)}",
            )

    # Create and return the connected mode tool
    description = (
        f"{base_description} Sends your request and waits for the collaborator's response. "
        "Use this tool ONLY to initiate a new collaboration request to another agent. "
        "When you receive a collaboration request, reply directly to the requesting agent with your result, clarification, or error—do NOT use this tool to reply to the same agent. "
        "The response might be the final result, a request for payment, or a request for clarification, requiring further action from you."
    )

    return StructuredTool.from_function(
        func=send_request,
        name="send_collaboration_request",
        description=description,
        args_schema=SendCollaborationRequestInput,
        return_direct=False,
        handle_tool_error=True,
        # coroutine=send_request_async,     #! TODO: Removed async coroutine temporarily
        metadata={"category": "collaboration"},
    )


def create_check_collaboration_result_tool(
    communication_hub: Optional[CommunicationHub] = None,
    agent_registry: Optional[AgentRegistry] = None,
    current_agent_id: Optional[str] = None,
) -> StructuredTool:
    """
    Create a tool for checking the status of previously sent collaboration requests.

    This tool is particularly useful for retrieving late responses that arrived
    after a timeout occurred in the original collaboration request.

    Args:
        communication_hub: Hub for agent communication
        agent_registry: Registry for accessing agent information
        current_agent_id: ID of the agent using the tool

    Returns:
        A StructuredTool for checking collaboration results
    """
    # Determine if we're in standalone mode
    standalone_mode = communication_hub is None or agent_registry is None

    # Common description base
    base_description = "Check if a previous collaboration request has completed and retrieve its result."

    if standalone_mode:
        # Standalone mode implementation
        def check_result_standalone(request_id: str) -> CheckCollaborationResultOutput:
            """Standalone implementation that explains limitations."""
            return CheckCollaborationResultOutput(
                success=False,
                status="not_available",
                response=(
                    f"Checking collaboration result for request '{request_id}' is not available in standalone mode. "
                    "Please continue with your own internal capabilities."
                ),
            )

        description = f"[STANDALONE MODE] {base_description} Note: In standalone mode, this tool will explain why checking results isn't available."

        return StructuredTool.from_function(
            func=check_result_standalone,
            name="check_collaboration_result",
            description=description,
            args_schema=CheckCollaborationResultInput,
            return_direct=False,
            metadata={"category": "collaboration"},
        )

    # Connected mode implementation
    async def check_result_async(request_id: str) -> CheckCollaborationResultOutput:
        """Check if a previous collaboration request has a result asynchronously."""
        # Check for late responses first
        if (
            hasattr(communication_hub, "late_responses")
            and request_id in communication_hub.late_responses
        ):
            logger.debug(f"Found late response for request {request_id}")
            response = communication_hub.late_responses[request_id]
            return CheckCollaborationResultOutput(
                success=True,
                status="completed_late",
                response=response.content,
            )

        # Check pending responses
        if request_id in communication_hub.pending_responses:
            future = communication_hub.pending_responses[request_id]
            if future.done() and not hasattr(future, "_timed_out"):
                try:
                    logger.debug(f"Found completed response for request {request_id}")
                    response = future.result()
                    return CheckCollaborationResultOutput(
                        success=True,
                        status="completed",
                        response=response.content,
                    )
                except Exception as e:
                    logger.error(f"Error getting result from future: {str(e)}")
                    return CheckCollaborationResultOutput(
                        success=False,
                        status="error",
                        response=f"Error retrieving response: {str(e)}",
                    )
            else:
                # Still pending
                return CheckCollaborationResultOutput(
                    success=False,
                    status="pending",
                    response="The collaboration request is still being processed. Try checking again later.",
                )

        # Request ID not found
        logger.warning(f"No result found for request ID: {request_id}")
        return CheckCollaborationResultOutput(
            success=False,
            status="not_found",
            response=f"No result found for request ID: {request_id}. The request may have been completed but not stored, or the ID may be incorrect.",
        )

    # Synchronous wrapper
    def check_result(request_id: str) -> CheckCollaborationResultOutput:
        """Check if a previous collaboration request has a result."""
        try:
            return asyncio.run(check_result_async(request_id))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(check_result_async(request_id))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in check_result: {str(e)}")
            return CheckCollaborationResultOutput(
                success=False,
                status="error",
                response=f"Error checking result: {str(e)}",
            )

    # Create and return the connected mode tool
    description = f"{base_description} This is useful for retrieving responses that arrived after the initial timeout period."

    return StructuredTool.from_function(
        func=check_result,
        name="check_collaboration_result",
        description=description,
        args_schema=CheckCollaborationResultInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=check_result_async,
        metadata={"category": "collaboration"},
    )
