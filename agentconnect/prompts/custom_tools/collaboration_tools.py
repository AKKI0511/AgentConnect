"""
Collaboration tools for agent workflows.

This module provides tools for agent search and collaboration within the AgentConnect framework.
These tools help agents find other specialized agents and collaborate on tasks.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypeVar

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import AgentType

logger = logging.getLogger(__name__)

# Type variables for better type hinting
T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


class AgentSearchInput(BaseModel):
    """Input schema for agent search."""

    capability_name: str = Field(description="Specific capability name to search for.")
    limit: int = Field(10, description="Maximum number of agents to return.")
    similarity_threshold: float = Field(
        0.2,
        description="Minimum similarity score (0-1) required for results. Higher values return only more relevant agents.",
    )


class AgentSearchOutput(BaseModel):
    """Output schema for agent search."""

    agent_ids: List[str] = Field(
        description="List of agent IDs with matching capabilities."
    )
    capabilities: List[Dict[str, Any]] = Field(
        description="List of capabilities for each agent."
    )


class SendCollaborationRequestInput(BaseModel):
    """Input schema for sending a collaboration request."""

    target_agent_id: str = Field(
        description="ID of the agent to collaborate with. (agent_id)"
    )
    task_description: str = Field(
        description="Description of the task to be performed."
    )
    timeout: int = Field(
        default=30, description="Maximum time to wait for a response in seconds."
    )

    class Config:
        """Config for the SendCollaborationRequestInput."""

        extra = "allow"  # Allow additional fields to be passed as kwargs


class SendCollaborationRequestOutput(BaseModel):
    """Output schema for sending a collaboration request."""

    success: bool = Field(description="Whether the request was sent successfully.")
    response: Optional[str] = Field(None, description="Response from the target agent.")


def create_agent_search_tool(
    agent_registry: AgentRegistry,
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

    # Synchronous implementation
    def search_agents(
        capability_name: str, limit: int = 10, similarity_threshold: float = 0.2
    ) -> Dict[str, Any]:
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
            return {
                "error": str(e),
                "agent_ids": [],
                "capabilities": [],
                "message": f"Error: Agent search failed - {str(e)}",
            }

    # Asynchronous implementation
    async def search_agents_async(
        capability_name: str, limit: int = 10, similarity_threshold: float = 0.2
    ) -> Dict[str, Any]:
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
            # Use the provided agent ID for filtering
            agent_id_for_filtering = current_agent_id

            # Find conversation partners and pending requests to exclude
            active_conversation_partners = []
            pending_request_partners = []
            recently_messaged_agents = []

            if agent_id_for_filtering:
                # Get the current agent to access its active conversations and pending requests
                if communication_hub:
                    current_agent = await communication_hub.get_agent(
                        agent_id_for_filtering
                    )
                    if current_agent:
                        # Get active conversations
                        if hasattr(current_agent, "active_conversations"):
                            active_conversation_partners = list(
                                current_agent.active_conversations.keys()
                            )
                            logger.debug(
                                f"Agent {agent_id_for_filtering} has active conversations with: {active_conversation_partners}"
                            )

                        # Get pending requests
                        if hasattr(current_agent, "pending_requests"):
                            pending_request_partners = list(
                                current_agent.pending_requests.keys()
                            )
                            logger.debug(
                                f"Agent {agent_id_for_filtering} has pending requests with: {pending_request_partners}"
                            )

                        # Check message history for recent communications
                        if (
                            hasattr(current_agent, "message_history")
                            and current_agent.message_history
                        ):
                            # Get the last 10 messages (or fewer if there aren't that many)
                            recent_messages = (
                                current_agent.message_history[-10:]
                                if len(current_agent.message_history) > 10
                                else current_agent.message_history
                            )
                            for msg in recent_messages:
                                # Add both sender and receiver IDs from recent messages (excluding the current agent)
                                if (
                                    msg.sender_id != agent_id_for_filtering
                                    and msg.sender_id not in recently_messaged_agents
                                ):
                                    recently_messaged_agents.append(msg.sender_id)
                                if (
                                    msg.receiver_id != agent_id_for_filtering
                                    and msg.receiver_id not in recently_messaged_agents
                                ):
                                    recently_messaged_agents.append(msg.receiver_id)

                            logger.debug(
                                f"Agent {agent_id_for_filtering} recently messaged with: {recently_messaged_agents}"
                            )

            # Combine all agents to exclude
            agents_to_exclude = list(
                set(
                    active_conversation_partners
                    + pending_request_partners
                    + recently_messaged_agents
                )
            )
            if agent_id_for_filtering:
                agents_to_exclude.append(agent_id_for_filtering)  # Also exclude self

            # Enhanced logging to show breakdown of excluded agents
            if agent_id_for_filtering:
                logger.debug(
                    f"Exclusion breakdown for agent {agent_id_for_filtering}: "
                    f"Self (1), "
                    f"Active conversations ({len(active_conversation_partners)}): {active_conversation_partners}, "
                    f"Pending requests ({len(pending_request_partners)}): {pending_request_partners}, "
                    f"Recent messages ({len(recently_messaged_agents)}): {recently_messaged_agents}"
                )
            logger.debug(
                f"Total agents excluded from search: {len(agents_to_exclude)} - {agents_to_exclude}"
            )

            # Check if agent_registry is available
            if agent_registry is None:
                logger.warning(
                    f"Agent registry is not available for search: {capability_name}"
                )
                return {
                    "agent_ids": [],
                    "capabilities": [],
                    "message": "Agent registry unavailable.",
                }

            # Try semantic search first for more flexible matching
            semantic_results = await agent_registry.get_by_capability_semantic(
                capability_name, limit=limit, similarity_threshold=similarity_threshold
            )

            # If semantic search returns results, use them
            if semantic_results:
                logger.debug(
                    f"Found {len(semantic_results)} agents via semantic search"
                )

                # Format the results
                agent_ids = []
                capabilities = []

                for agent, similarity in semantic_results:
                    # Skip human agents, the calling agent, and any agents we're already interacting with
                    if (
                        agent.agent_type == AgentType.HUMAN
                        or agent.agent_id in agents_to_exclude
                    ):
                        continue

                    agent_ids.append(agent.agent_id)

                    # Include all capabilities of the agent with their similarity scores
                    agent_capabilities = []
                    for capability in agent.capabilities:
                        agent_capabilities.append(
                            {
                                "name": capability.name,
                                "description": capability.description,
                                "similarity": round(
                                    float(similarity), 3
                                ),  # Convert to Python float and round to 3 decimal places
                            }
                        )

                    capabilities.append(
                        {
                            "agent_id": agent.agent_id,
                            "capabilities": agent_capabilities,
                        }
                    )

                # Log the filtering results
                if agent_id_for_filtering:
                    logger.debug(
                        f"After filtering (excluded {len(agents_to_exclude)} agents): "
                        f"Found {len(agent_ids)} agents for capability '{capability_name}'"
                    )

                return {
                    "agent_ids": agent_ids[:limit],
                    "capabilities": capabilities[:limit],
                    "message": "Note: Review capabilities carefully before collaborating. Similarity scores under 0.5 may indicate limited relevance to your request.",
                }

            # Fall back to exact matching if semantic search returns no results
            exact_results = await agent_registry.get_by_capability(
                capability_name, limit=limit, similarity_threshold=similarity_threshold
            )

            if exact_results:
                logger.debug(f"Found {len(exact_results)} agents via exact matching")

                # Format the results
                agent_ids = []
                capabilities = []

                for agent in exact_results:
                    # Skip human agents, the calling agent, and any agents we're already interacting with
                    if (
                        agent.agent_type == AgentType.HUMAN
                        or agent.agent_id in agents_to_exclude
                    ):
                        continue

                    agent_ids.append(agent.agent_id)

                    # Include all capabilities of the agent
                    agent_capabilities = []
                    for capability in agent.capabilities:
                        agent_capabilities.append(
                            {
                                "name": capability.name,
                                "description": capability.description,
                                "similarity": round(
                                    float(
                                        1.0
                                        if capability.name.lower()
                                        == capability_name.lower()
                                        else 0.0
                                    ),
                                    3,
                                ),
                            }
                        )

                    capabilities.append(
                        {
                            "agent_id": agent.agent_id,
                            "capabilities": agent_capabilities,
                        }
                    )

                # Log the filtering results
                if agent_id_for_filtering:
                    logger.debug(
                        f"After filtering (excluded {len(agents_to_exclude)} agents): "
                        f"Found {len(agent_ids)} agents for capability '{capability_name}'"
                    )

                return {
                    "agent_ids": agent_ids[:limit],
                    "capabilities": capabilities[:limit],
                    "message": "Note: Review capabilities carefully before collaborating. Similarity scores under 0.5 may indicate limited relevance to your request.",
                }

            # No results found
            logger.debug(
                f"No agents found for '{capability_name}'. Try different search term."
            )

            # As a last resort, get all agents and return them with a message
            try:
                all_agents = await agent_registry.get_all_agents()

                if all_agents:
                    logger.debug(f"Returning all {len(all_agents)} agents as fallback")

                    # Format the results
                    agent_ids = []
                    capabilities = []

                    for agent in all_agents:
                        # Skip human agents, the calling agent, and any agents we're already interacting with
                        if (
                            agent.agent_type == AgentType.HUMAN
                            or agent.agent_id in agents_to_exclude
                        ):
                            continue

                        agent_ids.append(agent.agent_id)

                        # Include all capabilities of the agent
                        agent_capabilities = []
                        for capability in agent.capabilities:
                            agent_capabilities.append(
                                {
                                    "name": capability.name,
                                    "description": capability.description,
                                    "similarity": round(
                                        float(
                                            1.0
                                            if capability.name.lower()
                                            == capability_name.lower()
                                            else 0.0
                                        ),
                                        3,
                                    ),
                                }
                            )

                        capabilities.append(
                            {
                                "agent_id": agent.agent_id,
                                "capabilities": agent_capabilities,
                            }
                        )

                    # Log the filtering results
                    if agent_id_for_filtering:
                        logger.debug(
                            f"After filtering (excluded {len(agents_to_exclude)} agents): "
                            f"Found {len(agent_ids)} agents as fallback"
                        )

                    return {
                        "agent_ids": agent_ids[:limit],
                        "capabilities": capabilities[:limit],
                        "message": f"No specific agents for '{capability_name}'. Showing all available agents. Review capabilities carefully before collaborating.",
                    }
            except Exception as e:
                logger.error(f"Error getting all agents: {str(e)}")

            return {
                "agent_ids": [],
                "capabilities": [],
                "message": f"No agents found for '{capability_name}'. Try different search term.",
            }
        except Exception as e:
            logger.error(f"Error searching for agents: {str(e)}")
            return {"error": str(e), "agent_ids": [], "capabilities": []}

    # Create a description that includes available capabilities if possible
    description = "Search for agents with specific capabilities. Uses semantic matching to find agents with relevant capabilities."

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
    communication_hub: CommunicationHub,
    agent_registry: AgentRegistry,
    current_agent_id: str,
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
    # Capture the current agent ID at tool creation time
    creator_agent_id = current_agent_id
    logger.info(f"Creating collaboration request tool for agent: {creator_agent_id}")

    # If no agent ID is set, create a tool that returns an error when used
    if not creator_agent_id:
        logger.warning(
            "Creating collaboration request tool with no agent ID set - will return error when used"
        )

        # Synchronous implementation that returns an error
        def error_request(
            target_agent_id: str, task_description: str, timeout: int = 30, **kwargs
        ) -> Dict[str, Any]:
            """Send a collaboration request to another agent."""
            return {
                "success": False,
                "response": "Error: Tool not properly initialized. Contact administrator.",
            }

        # Create the tool with the error implementation
        return StructuredTool.from_function(
            func=error_request,
            name="send_collaboration_request",
            description="Sends a collaboration request to a specific agent and waits for a response. Use this after finding an agent with search_for_agents to delegate tasks.",
            args_schema=SendCollaborationRequestInput,
            return_direct=False,
            handle_tool_error=True,
            metadata={"category": "collaboration"},
        )

    # Normal implementation when agent ID is set
    # Synchronous implementation
    def send_request(
        target_agent_id: str, task_description: str, timeout: int = 30, **kwargs
    ) -> Dict[str, Any]:
        """Send a collaboration request to another agent."""
        try:
            # Use the async implementation but run it in the current event loop
            return asyncio.run(
                send_request_async(target_agent_id, task_description, timeout, **kwargs)
            )
        except RuntimeError:
            # If we're already in an event loop, create a new one
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    send_request_async(
                        target_agent_id, task_description, timeout, **kwargs
                    )
                )
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in send_request: {str(e)}")
            return {
                "success": False,
                "response": f"Error sending collaboration request: {str(e)}",
            }

    # Asynchronous implementation
    async def send_request_async(
        target_agent_id: str,
        task_description: str,
        timeout: int = 30,
        **kwargs,  # Additional data
    ) -> Dict[str, Any]:
        """Send a collaboration request to another agent asynchronously."""
        # Always use the captured agent ID from tool creation time
        # This ensures we use the correct agent ID even if current_agent_id changes
        sender_id = creator_agent_id

        if not sender_id:
            logger.error("No sender_id available for collaboration request")
            return {
                "success": False,
                "response": "Error: Tool not properly initialized with agent context",
            }

        # Check if required dependencies are available
        if communication_hub is None:
            logger.error("Communication hub is not available for collaboration request")
            return {
                "success": False,
                "response": "Error: Communication hub unavailable.",
            }

        if agent_registry is None:
            logger.error("Agent registry is not available for collaboration request")
            return {
                "success": False,
                "response": "Error: Agent registry unavailable.",
            }

        logger.info(
            f"COLLABORATION REQUEST: Using sender_id={sender_id} to send request to target_agent_id={target_agent_id}"
        )

        # Check if we're trying to send a request to ourselves
        if sender_id == target_agent_id:
            logger.error(
                f"Cannot send collaboration request to yourself: {sender_id} -> {target_agent_id}"
            )
            return {
                "success": False,
                "response": "Error: Cannot send request to yourself.",
            }

        # Check if the target agent exists
        if not await communication_hub.is_agent_active(target_agent_id):
            return {
                "success": False,
                "response": f"Error: Agent {target_agent_id} not found.",
            }

        # Check if the target agent is a human agent
        if await agent_registry.get_agent_type(target_agent_id) == AgentType.HUMAN:
            return {
                "success": False,
                "response": "Error: Cannot send requests to human agents.",
            }

        # Add retry tracking to prevent infinite loops
        # Use a shorter timeout to prevent long waits
        adjusted_timeout = min(timeout, 90)  # Cap timeout at 90 seconds

        # Add metadata to track the collaboration chain
        metadata = kwargs.copy() if kwargs else {}
        if "collaboration_chain" not in metadata:
            metadata["collaboration_chain"] = []

        # Add the current agent to the collaboration chain
        if sender_id not in metadata["collaboration_chain"]:
            metadata["collaboration_chain"].append(sender_id)

        # Check if we're creating a loop in the collaboration chain
        if target_agent_id in metadata["collaboration_chain"]:
            return {
                "success": False,
                "response": f"Error: Detected loop in collaboration chain with {target_agent_id}.",
            }

        # Check if the original sender is in the collaboration chain
        # and prevent sending a request back to the original sender
        if (
            "original_sender" in metadata
            and metadata["original_sender"] == target_agent_id
        ):
            return {
                "success": False,
                "response": f"Error: Cannot send request back to original sender {target_agent_id}.",
            }

        # If this is the first agent in the chain, store the original sender
        if len(metadata["collaboration_chain"]) == 1:
            metadata["original_sender"] = metadata["collaboration_chain"][0]

        # Limit the collaboration chain length to prevent deep recursion
        if len(metadata["collaboration_chain"]) > 5:
            return {
                "success": False,
                "response": "Error: Collaboration chain too long. Simplify request.",
            }

        try:
            # Send the collaboration request
            logger.info(
                f"Sending collaboration request from {sender_id} to {target_agent_id}"
            )

            # Ensure we're using the correct sender_id
            response = await communication_hub.send_collaboration_request(
                sender_id=sender_id,  # Use the current agent's ID
                receiver_id=target_agent_id,
                task_description=task_description,
                timeout=adjusted_timeout,
                **metadata,
            )

            # Log the response for debugging
            if response is None:
                logger.warning(
                    f"Received None response from send_collaboration_request to {target_agent_id}"
                )
                return {
                    "success": False,
                    "response": f"No response from {target_agent_id} within {adjusted_timeout} seconds.",
                    "error": "timeout",
                }
            else:
                logger.info(
                    f"Received response from {target_agent_id}: {response[:100]}..."
                )

            # For normal responses, return as is
            return {"success": True, "response": response}

        except Exception as e:
            logger.exception(f"Error sending collaboration request: {str(e)}")
            return {
                "success": False,
                "response": f"Error: Collaboration failed - {str(e)}",
                "error": "collaboration_exception",
            }

    # Create and return the tool
    return StructuredTool.from_function(
        func=send_request,
        name="send_collaboration_request",
        description="Sends a collaboration request to a specific agent and waits for a response. Use after finding an agent with search_for_agents.",
        args_schema=SendCollaborationRequestInput,
        return_direct=False,
        handle_tool_error=True,
        metadata={"category": "collaboration"},
    )
