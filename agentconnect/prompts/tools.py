"""
Tool definitions for the AgentConnect framework.

This module provides tools that agents can use to interact with each other,
search for specialized agents, and collaborate on tasks. These tools are
designed to be used with LangGraph workflows and LLM-based agents.

Key components:
- Agent search tools: Find agents with specific capabilities
- Collaboration tools: Send requests to other agents and manage responses
- Task decomposition tools: Break complex tasks into manageable subtasks
- Tool registry: Central registry for managing available tools

The tools in this module are designed to be used within the agent's workflow
to enable seamless agent-to-agent communication and collaboration.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, TypeVar

from langchain.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser

# Standard library imports
from pydantic import BaseModel, Field

# Absolute imports from agentconnect package
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import AgentType

logger = logging.getLogger(__name__)

# Type variables for better type hinting
T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


# Define the output schema for structured output
class Subtask(BaseModel):
    """A subtask to be completed by an agent."""

    id: str = Field(description="Unique identifier for the subtask")
    title: str = Field(description="Clear title that summarizes the subtask")
    description: str = Field(description="Brief description of what needs to be done")
    status: str = Field(default="pending", description="Current status of the subtask")


class TaskDecompositionResult(BaseModel):
    """The result of task decomposition."""

    subtasks: List[Subtask] = Field(description="List of subtasks")
    original_task: str = Field(description="The original task that was decomposed")


# Input schemas
class AgentSearchInput(BaseModel):
    """Input schema for agent search."""

    capability_name: str = Field(description="Specific capability name to search for.")
    limit: int = Field(10, description="Maximum number of agents to return.")


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


class TaskDecompositionInput(BaseModel):
    """Input schema for task decomposition."""

    task_description: str = Field(description="Description of the task to decompose.")
    max_subtasks: int = Field(
        default=5, description="Maximum number of subtasks to create."
    )


class TaskDecompositionOutput(BaseModel):
    """Output schema for task decomposition."""

    subtasks: List[Dict[str, Any]] = Field(
        description="List of subtasks with descriptions."
    )


class ToolRegistry:
    """
    Registry for all available tools that can be used by agents.

    This class provides a centralized registry for managing the tools available to agents.
    It allows for registering, retrieving, and categorizing tools, enabling agents to
    access the right tools for specific tasks.

    Tools can be organized by categories (e.g., 'collaboration', 'task_management')
    to make it easier for agents to discover relevant tools.
    """

    def __init__(self):
        """
        Initialize an empty tool registry.

        The registry starts with no tools and will be populated through register_tool calls.
        """
        self._tools: Dict[str, StructuredTool] = {}

    def register_tool(self, tool: StructuredTool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: The StructuredTool to register

        Note:
            If a tool with the same name already exists, it will be overwritten.
        """
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[StructuredTool]:
        """
        Get a tool by name.

        Args:
            name: The name of the tool to retrieve

        Returns:
            The tool if found, None otherwise
        """
        return self._tools.get(name)

    def get_all_tools(self) -> List[StructuredTool]:
        """
        Get all registered tools.

        Returns:
            A list of all tools in the registry
        """
        return list(self._tools.values())

    def get_tools_by_category(self, category: str) -> List[StructuredTool]:
        """
        Get all tools in a specific category.

        Args:
            category: The category to filter tools by

        Returns:
            A list of tools in the specified category
        """
        return [
            tool
            for tool in self._tools.values()
            if tool.metadata and tool.metadata.get("category") == category
        ]


class PromptTools:
    """
    Class for creating and managing tools for agent prompts.

    This class is responsible for creating, registering, and managing the tools
    that agents can use to perform actions such as searching for other agents,
    sending collaboration requests, and decomposing tasks.

    Each agent has its own isolated set of tools through a dedicated ToolRegistry
    instance, ensuring that tools are properly configured for the specific agent
    using them.

    Attributes:
        agent_registry: Registry for accessing agent information
        communication_hub: Hub for agent communication
        llm: Optional language model for tools that require LLM capabilities
        _current_agent_id: ID of the agent currently using these tools
        _tool_registry: Registry for managing available tools
        _available_capabilities: Cached list of available capabilities
        _agent_specific_tools_registered: Flag indicating if agent-specific tools are registered
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        communication_hub: CommunicationHub,
        llm=None,
    ):
        """
        Initialize the PromptTools class.

        Args:
            agent_registry: Registry for accessing agent information and capabilities
            communication_hub: Hub for agent communication and message passing
            llm: Optional language model for tools that require LLM capabilities
        """
        self.agent_registry = agent_registry
        self.communication_hub = communication_hub
        self._current_agent_id = None
        # Always create a new ToolRegistry for each PromptTools instance
        # This ensures each agent has its own isolated set of tools
        self._tool_registry = ToolRegistry()
        self._available_capabilities = []
        self.llm = llm
        self._agent_specific_tools_registered = False

        # Register default tools that don't require an agent ID
        self._register_basic_tools()

    def _register_basic_tools(self) -> None:
        """
        Register the basic set of tools that don't require an agent ID.

        This method initializes tools like task decomposition that can
        function without knowing which agent is using them.
        """
        self._tool_registry.register_tool(self.create_task_decomposition_tool())

    def _register_agent_specific_tools(self) -> None:
        """
        Register tools that require an agent ID to be set.

        This method registers tools that need agent context, such as agent search
        and collaboration request tools. These tools need to know which agent is
        making the request to properly handle permissions and collaboration chains.

        Note:
            This method will log a warning and do nothing if no agent ID is set.
        """
        if not self._current_agent_id:
            logger.warning("Cannot register agent-specific tools: No agent ID set")
            return

        # Only register these tools if they haven't been registered yet
        if not self._agent_specific_tools_registered:
            self._tool_registry.register_tool(self.create_agent_search_tool())
            self._tool_registry.register_tool(
                self.create_send_collaboration_request_tool()
            )
            self._agent_specific_tools_registered = True
            logger.debug(
                f"Registered agent-specific tools for agent: {self._current_agent_id}"
            )

    def create_tool_from_function(
        self,
        func: Callable[..., Any],
        name: str,
        description: str,
        args_schema: Type[T],
        category: Optional[str] = None,
        coroutine: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> StructuredTool:
        """
        Create a tool from a function with proper async support.

        This method creates a LangChain StructuredTool that can be used in agent workflows.
        It supports both synchronous and asynchronous implementations of the tool,
        allowing for efficient handling of I/O-bound operations.

        The tool is automatically registered in the tool registry with the specified
        category, making it available for agent use.

        Args:
            func: The synchronous function implementation
            name: Name of the tool (must be unique)
            description: Description of the tool that will be shown to the agent
            args_schema: Pydantic model for the tool's arguments validation
            category: Optional category for the tool (e.g., 'collaboration', 'task_management')
            coroutine: Optional async implementation of the function for better performance

        Returns:
            A StructuredTool that can be used in LangChain workflows

        Note:
            If both sync and async implementations are provided, the async version
            will be used when the agent is running in an async context.
        """
        # Create the tool with both sync and async implementations if available
        tool = StructuredTool.from_function(
            func=func,
            name=name,
            description=description,
            args_schema=args_schema,
            return_direct=False,
            handle_tool_error=True,
            coroutine=coroutine,
        )

        # Register the tool with the category
        if category:
            tool.metadata = tool.metadata or {}
            tool.metadata["category"] = category

        # Register the tool
        self._tool_registry.register_tool(tool)

        return tool

    def create_agent_search_tool(self) -> StructuredTool:
        """Create a tool for searching agents by capability."""

        # Synchronous implementation
        def search_agents(capability_name: str, limit: int = 10) -> Dict[str, Any]:
            """Search for agents with a specific capability."""
            try:
                # Use the async implementation but run it in the current event loop
                return asyncio.run(search_agents_async(capability_name, limit))
            except RuntimeError:
                # If we're already in an event loop, create a new one
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        search_agents_async(capability_name, limit)
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
            capability_name: str, limit: int = 10
        ) -> Dict[str, Any]:
            """Search for agents with a specific capability."""
            logger.debug(f"Searching for agents with capability: {capability_name}")

            try:
                # Get the current agent ID for filtering
                current_agent_id = self._current_agent_id

                # Check if agent_registry is available
                if self.agent_registry is None:
                    logger.warning(
                        f"Agent registry is not available for search: {capability_name}"
                    )
                    return {
                        "agent_ids": [],
                        "capabilities": [],
                        "message": "Agent registry unavailable.",
                    }

                # Try semantic search first for more flexible matching
                semantic_results = await self.agent_registry.get_by_capability_semantic(
                    capability_name
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
                        # Skip human agents and the calling agent (if we know who the calling agent is)
                        if agent.agent_type == AgentType.HUMAN or (
                            current_agent_id and agent.agent_id == current_agent_id
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
                                    "similarity": similarity,  # Include the similarity score
                                }
                            )

                        capabilities.append(
                            {
                                "agent_id": agent.agent_id,
                                "capabilities": agent_capabilities,
                            }
                        )

                    return {
                        "agent_ids": agent_ids[:limit],
                        "capabilities": capabilities[:limit],
                    }

                # Fall back to exact matching if semantic search returns no results
                exact_results = await self.agent_registry.get_by_capability(
                    capability_name
                )

                if exact_results:
                    logger.debug(
                        f"Found {len(exact_results)} agents via exact matching"
                    )

                    # Format the results
                    agent_ids = []
                    capabilities = []

                    for agent in exact_results:
                        # Skip human agents and the calling agent (if we know who the calling agent is)
                        if agent.agent_type == AgentType.HUMAN or (
                            current_agent_id and agent.agent_id == current_agent_id
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
                                }
                            )

                        capabilities.append(
                            {
                                "agent_id": agent.agent_id,
                                "capabilities": agent_capabilities,
                            }
                        )

                    return {
                        "agent_ids": agent_ids[:limit],
                        "capabilities": capabilities[:limit],
                    }

                # No results found
                logger.debug(
                    f"No agents found for '{capability_name}'. Try different search term."
                )

                # As a last resort, get all agents and return them with a message
                try:
                    all_agents = await self.agent_registry.get_all_agents()

                    if all_agents:
                        logger.debug(
                            f"Returning all {len(all_agents)} agents as fallback"
                        )

                        # Format the results
                        agent_ids = []
                        capabilities = []

                        for agent in all_agents:
                            # Skip human agents and the calling agent (if we know who the calling agent is)
                            if agent.agent_type == AgentType.HUMAN or (
                                current_agent_id and agent.agent_id == current_agent_id
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
                                    }
                                )

                            capabilities.append(
                                {
                                    "agent_id": agent.agent_id,
                                    "capabilities": agent_capabilities,
                                }
                            )

                        return {
                            "agent_ids": agent_ids[:limit],
                            "capabilities": capabilities[:limit],
                            "message": f"No specific agents for '{capability_name}'. Showing all available agents.",
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

        # Get available capabilities for the tool description
        available_capabilities = []
        try:
            # Try to use stored capabilities first
            if (
                hasattr(self, "_available_capabilities")
                and self._available_capabilities
            ):
                available_capabilities = self._available_capabilities
            elif (
                self.agent_registry is not None
            ):  # Only try to get capabilities if agent_registry is available
                # Create a task to update capabilities in the background
                async def update_capabilities():
                    try:
                        capabilities = await self.agent_registry.get_all_capabilities()
                        self._available_capabilities = capabilities
                        return capabilities
                    except Exception as e:
                        logger.warning(f"Error getting capabilities: {str(e)}")
                        return []

                # Run the task in the background if possible
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(update_capabilities())
                    else:
                        available_capabilities = asyncio.run(update_capabilities())
                except RuntimeError:
                    # If we can't get a running loop, create a new one
                    loop = asyncio.new_event_loop()
                    try:
                        available_capabilities = loop.run_until_complete(
                            update_capabilities()
                        )
                    finally:
                        loop.close()
            else:
                # Use default capabilities if agent_registry is not available
                default_capabilities = [
                    "research",
                    "summarization",
                    "fact_checking",
                    "data_analysis",
                    "content_creation",
                    "translation",
                    "code_generation",
                    "question_answering",
                ]
                logger.debug(f"Using default capabilities: {default_capabilities}")
                available_capabilities = default_capabilities
                self._available_capabilities = default_capabilities
        except Exception as e:
            logger.warning(f"Failed to get capabilities: {str(e)}")
            # Fallback to default capabilities
            default_capabilities = [
                "research",
                "summarization",
                "fact_checking",
                "data_analysis",
                "content_creation",
                "translation",
                "code_generation",
                "question_answering",
            ]
            logger.debug(f"Using fallback default capabilities: {default_capabilities}")
            available_capabilities = default_capabilities

        # Create a description that includes available capabilities if possible
        description = "Search for agents with specific capabilities. "

        # Use stored capabilities if available
        if available_capabilities:
            capability_examples = ", ".join(available_capabilities[:5])
            if len(available_capabilities) > 5:
                description += f"Examples: {capability_examples} and others. Uses semantic matching."
            else:
                description += (
                    f"Available: {capability_examples}. Uses semantic matching."
                )
        else:
            description += (
                "Uses semantic matching to find agents with relevant capabilities."
            )

        return self.create_tool_from_function(
            func=search_agents,
            name="search_for_agents",
            description=description,
            args_schema=AgentSearchInput,
            category="collaboration",
            coroutine=search_agents_async,
        )

    def create_send_collaboration_request_tool(self) -> StructuredTool:
        """Create a tool for sending collaboration requests to other agents."""

        # Capture the current agent ID at tool creation time
        creator_agent_id = self._current_agent_id
        logger.info(
            f"Creating collaboration request tool for agent: {creator_agent_id}"
        )

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
            return self.create_tool_from_function(
                func=error_request,
                name="send_collaboration_request",
                description="Sends a collaboration request to a specific agent and waits for a response. Use this after finding an agent with search_for_agents to delegate tasks.",
                args_schema=SendCollaborationRequestInput,
                category="collaboration",
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
                    send_request_async(
                        target_agent_id, task_description, timeout, **kwargs
                    )
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
            # This ensures we use the correct agent ID even if _current_agent_id changes
            sender_id = creator_agent_id

            if not sender_id:
                logger.error("No sender_id available for collaboration request")
                return {
                    "success": False,
                    "response": "Error: Tool not properly initialized with agent context",
                }

            # Check if required dependencies are available
            if self.communication_hub is None:
                logger.error(
                    "Communication hub is not available for collaboration request"
                )
                return {
                    "success": False,
                    "response": "Error: Communication hub unavailable.",
                }

            if self.agent_registry is None:
                logger.error(
                    "Agent registry is not available for collaboration request"
                )
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
            if not await self.communication_hub.is_agent_active(target_agent_id):
                return {
                    "success": False,
                    "response": f"Error: Agent {target_agent_id} not found.",
                }

            # Check if the target agent is a human agent
            if (
                await self.agent_registry.get_agent_type(target_agent_id)
                == AgentType.HUMAN
            ):
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
                response = await self.communication_hub.send_collaboration_request(
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

        return self.create_tool_from_function(
            func=send_request,
            name="send_collaboration_request",
            description="Sends a collaboration request to a specific agent and waits for a response. Use after finding an agent with search_for_agents.",
            args_schema=SendCollaborationRequestInput,
            category="collaboration",
        )

    async def _fallback_task_decomposition(
        self, task_description: str, max_subtasks: int = 5, subtasks_text: str = None
    ) -> Dict[str, Any]:
        """Fallback method for task decomposition when structured output fails."""
        if subtasks_text is None:
            subtasks_text = """
            1. Analyze the task: Understand requirements and scope
            2. Research information: Gather necessary data
            3. Formulate solution: Develop comprehensive approach
            """

        # Parse the subtasks
        subtasks = []
        import re

        # Simple regex to extract numbered items
        pattern = r"(\d+)\.\s+(.*?)(?=\n\s*\d+\.|\Z)"
        matches = re.findall(pattern, subtasks_text, re.DOTALL)

        for i, (_, content) in enumerate(matches):
            if i >= max_subtasks:
                break

            # Split by colon if present
            parts = content.split(":", 1)
            title = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else title

            subtasks.append(
                {
                    "id": str(i + 1),
                    "title": title,
                    "description": description,
                    "status": "pending",
                }
            )

        # If no subtasks were found, create a simple fallback
        if not subtasks:
            # Split by lines and look for numbered items
            lines = subtasks_text.split("\n")
            for i, line in enumerate(lines):
                if i >= max_subtasks:
                    break

                line = line.strip()
                if re.match(r"^\d+\.", line):
                    # Remove the number and period
                    content = re.sub(r"^\d+\.\s*", "", line)

                    # Split by colon if present
                    parts = content.split(":", 1)
                    title = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else title

                    subtasks.append(
                        {
                            "id": str(len(subtasks) + 1),
                            "title": title,
                            "description": description,
                            "status": "pending",
                        }
                    )

        return {"subtasks": subtasks, "original_task": task_description}

    def create_task_decomposition_tool(self) -> StructuredTool:
        """
        Create a tool for decomposing complex tasks into subtasks.

        This tool helps agents break down complex tasks into smaller, more manageable
        subtasks. It's useful for organizing and prioritizing work, especially for
        multi-step processes that would be difficult to tackle as a single unit.

        The tool uses the LLM to analyze the task and create a structured decomposition
        with clear, actionable subtasks. Each subtask includes a unique ID, title,
        and description.

        Returns:
            A StructuredTool for task decomposition that can be used in agent workflows

        Note:
            If the LLM is not available, the tool will fall back to a simple
            rule-based decomposition.
        """

        # Synchronous implementation
        def decompose_task(
            task_description: str, max_subtasks: int = 5
        ) -> Dict[str, Any]:
            """
            Decompose a complex task into smaller, manageable subtasks.

            This is the synchronous wrapper for the task decomposition functionality.
            It handles event loop management to ensure the async implementation can
            be called from both sync and async contexts.

            Args:
                task_description: Description of the task to decompose
                max_subtasks: Maximum number of subtasks to create (default: 5)

            Returns:
                Dictionary containing the list of subtasks and the original task

            Raises:
                RuntimeError: If there's an issue with the event loop management
            """
            try:
                # Use the async implementation but run it in the current event loop
                return asyncio.run(decompose_task_async(task_description, max_subtasks))
            except RuntimeError:
                # If we're already in an event loop, create a new one
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        decompose_task_async(task_description, max_subtasks)
                    )
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error in decompose_task: {str(e)}")
                return {
                    "subtasks": [],
                    "message": f"Error: Task decomposition failed - {str(e)}",
                }

        # Asynchronous implementation
        async def decompose_task_async(
            task_description: str, max_subtasks: int = 5
        ) -> Dict[str, Any]:
            """
            Decompose a complex task into smaller, manageable subtasks asynchronously.

            This is the core implementation of the task decomposition functionality.
            It uses the LLM to analyze the task and create a structured list of subtasks.

            Args:
                task_description: Description of the task to decompose
                max_subtasks: Maximum number of subtasks to create (default: 5)

            Returns:
                Dictionary containing the list of subtasks and the original task

            Note:
                If the LLM fails to generate a proper JSON response, the method
                will fall back to manual parsing of the text response.
            """
            # Create the output parser
            parser = JsonOutputParser(pydantic_object=TaskDecompositionResult)

            # Create the system prompt with optimized structure
            system_prompt = f"""You are a task decomposition specialist.

Task Description: {task_description}
Maximum Subtasks: {max_subtasks}

DECISION FRAMEWORK:
1. ASSESS: Analyze the complexity of the task
2. EXECUTE: Break down into clear, actionable subtasks
3. RESPOND: Format as a structured list

TASK DECOMPOSITION:
1. Break down the task into clear, actionable subtasks
2. Each subtask should be 1-2 sentences maximum
3. Identify dependencies between subtasks when necessary
4. Limit to {max_subtasks} subtasks or fewer

{parser.get_format_instructions()}

Make sure each subtask has a unique ID, a clear title, and a concise description.
"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=f"Break down this task into at most {max_subtasks} subtasks: {task_description}"
                ),
            ]

            try:
                # Use the LLM to decompose the task
                if self.llm:
                    # Use the LLM with structured output
                    response = await self.llm.ainvoke(messages)

                    try:
                        # Try to parse the response as JSON
                        result = parser.parse(response.content)
                        return result
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse LLM response as JSON: {str(e)}"
                        )
                        # Fall back to manual parsing if JSON parsing fails
                        return await self._fallback_task_decomposition(
                            task_description, max_subtasks, response.content
                        )
                else:
                    # Fallback to a simple decomposition
                    return await self._fallback_task_decomposition(
                        task_description, max_subtasks
                    )
            except Exception as e:
                logger.error(f"Error in decompose_task_async: {str(e)}")
                # Return a simple fallback decomposition on error
                return {
                    "error": str(e),
                    "subtasks": [
                        {
                            "id": "1",
                            "title": "Analyze the task",
                            "description": f"Understand requirements and scope: {task_description}",
                            "status": "pending",
                        },
                        {
                            "id": "2",
                            "title": "Research information",
                            "description": "Gather necessary data for the task",
                            "status": "pending",
                        },
                        {
                            "id": "3",
                            "title": "Formulate solution",
                            "description": "Develop approach based on analysis and research",
                            "status": "pending",
                        },
                    ],
                    "original_task": task_description,
                }

        return self.create_tool_from_function(
            func=decompose_task,
            name="decompose_task",
            description="Breaks down a complex task into smaller, manageable subtasks. Use this when faced with a multi-step or complex request.",
            args_schema=TaskDecompositionInput,
            category="task_management",
            coroutine=decompose_task_async,
        )

    def set_current_agent(self, agent_id: str) -> None:
        """
        Set the current agent ID for context in tools.

        This method establishes the context for which agent is using the tools,
        which is essential for agent-specific tools like collaboration requests.
        It also triggers the registration of agent-specific tools if they haven't
        been registered yet.

        Args:
            agent_id: The ID of the agent currently using the tools

        Note:
            This method logs whenever the agent context changes to help with debugging
            and tracing agent interactions.
        """
        if hasattr(self, "_current_agent_id") and self._current_agent_id != agent_id:
            logger.info(
                f"AGENT CONTEXT CHANGE: Changing current agent from {self._current_agent_id} to {agent_id}"
            )
        else:
            logger.info(f"AGENT CONTEXT SET: Setting current agent to {agent_id}")

        self._current_agent_id = agent_id

        # Register agent-specific tools now that we have an agent ID
        self._register_agent_specific_tools()

    def get_tools_for_workflow(
        self, categories: Optional[List[str]] = None, agent_id: Optional[str] = None
    ) -> List[StructuredTool]:
        """
        Get tools for a specific workflow based on categories.

        This method retrieves the appropriate tools for a workflow, optionally
        filtered by category. It's used by agent workflows to get the tools
        they need for specific tasks.

        Args:
            categories: List of tool categories to include (e.g., 'collaboration', 'task_management')
            agent_id: ID of the agent that will use these tools (for logging only, doesn't change context)

        Returns:
            List of StructuredTool instances configured for the agent

        Note:
            If categories is None, all tools in the registry will be returned.
            The agent_id parameter is used only for logging and doesn't change
            the current agent context.
        """
        # Log which agent is requesting tools, but don't change the current agent context
        if agent_id:
            logger.debug(f"Getting tools for agent: {agent_id}")

        if categories:
            tools = []
            for category in categories:
                tools.extend(self._tool_registry.get_tools_by_category(category))
            return tools
        else:
            return self._tool_registry.get_all_tools()
