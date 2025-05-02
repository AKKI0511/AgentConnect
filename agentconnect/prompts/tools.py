"""
Tool definitions for the AgentConnect framework.

This module provides tools that agents can use to interact with each other,
search for specialized agents, and collaborate on tasks. These tools are
designed to be used with LangGraph workflows and LLM-based agents.

Key components:

- **Agent search tools**: Find agents with specific capabilities
- **Collaboration tools**: Send requests to other agents and manage responses
- **Task decomposition tools**: Break complex tasks into manageable subtasks
- **Tool registry**: Central registry for managing available tools

The tools in this module are designed to be used within the agent's workflow
to enable seamless agent-to-agent communication and collaboration.
"""

import logging
from typing import Any, Awaitable, Callable, List, Optional, Type, TypeVar

from langchain.tools import StructuredTool

# Standard library imports
from pydantic import BaseModel

# Absolute imports from agentconnect package
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.prompts.custom_tools.registry import ToolRegistry

# Import implementations from custom_tools
from agentconnect.prompts.custom_tools.collaboration_tools import (
    create_agent_search_tool,
    create_send_collaboration_request_tool,
    create_check_collaboration_result_tool,
)
from agentconnect.prompts.custom_tools.task_tools import create_task_decomposition_tool

logger = logging.getLogger(__name__)

# Type variables for better type hinting
T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


class PromptTools:
    """
    Class for creating and managing tools for agent prompts.

    This class is responsible for creating, registering, and managing the tools
    that agents can use to perform actions such as searching for other agents,
    sending collaboration requests, and decomposing tasks.

    Each agent has its own isolated set of tools through a dedicated ToolRegistry
    instance, ensuring that tools are properly configured for the specific agent
    using them.

    The class supports both connected mode (with registry and hub) and standalone mode
    (without registry and hub, for direct chat interactions).

    Attributes:
        agent_registry: Registry for accessing agent information, can be None in standalone mode
        communication_hub: Hub for agent communication, can be None in standalone mode
        llm: Optional language model for tools that require LLM capabilities
        _current_agent_id: ID of the agent currently using these tools
        _tool_registry: Registry for managing available tools
        _available_capabilities: Cached list of available capabilities
        _agent_specific_tools_registered: Flag indicating if agent-specific tools are registered
        _is_standalone_mode: Flag indicating if operating in standalone mode (without registry/hub)
    """

    def __init__(
        self,
        agent_registry: Optional[AgentRegistry] = None,
        communication_hub: Optional[CommunicationHub] = None,
        llm=None,
    ):
        """
        Initialize the PromptTools class.

        Args:
            agent_registry: Registry for accessing agent information and capabilities.
                           Can be None for standalone mode.
            communication_hub: Hub for agent communication and message passing.
                             Can be None for standalone mode.
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

        # Detect if we're in standalone mode (no registry or hub)
        self._is_standalone_mode = agent_registry is None or communication_hub is None

        if self._is_standalone_mode:
            logger.info("PromptTools initialized in standalone mode (no registry/hub)")

        # Register default tools that don't require an agent ID
        self._register_basic_tools()

    def _register_basic_tools(self) -> None:
        """
        Register the basic set of tools that don't require an agent ID.

        This method initializes tools like task decomposition that can
        function without knowing which agent is using them.
        """
        # Create and register the task decomposition tool
        task_decomposition_tool = create_task_decomposition_tool(self.llm)
        self._tool_registry.register_tool(task_decomposition_tool)

    def _register_agent_specific_tools(self) -> None:
        """
        Register tools that require an agent ID to be set.

        This method registers tools that need agent context, such as agent search
        and collaboration request tools. In standalone mode, it registers alternative
        versions of these tools that explain the limitations.

        Note:
            This method will log a warning and do nothing if no agent ID is set.
        """
        if not self._current_agent_id:
            logger.warning("Cannot register agent-specific tools: No agent ID set")
            return

        # Only register these tools if they haven't been registered yet
        if not self._agent_specific_tools_registered:
            # Create the agent search tool (handles standalone mode internally)
            agent_search_tool = create_agent_search_tool(
                self.agent_registry, self._current_agent_id, self.communication_hub
            )

            # Create the collaboration request tool (handles standalone mode internally)
            collaboration_request_tool = create_send_collaboration_request_tool(
                self.communication_hub, self.agent_registry, self._current_agent_id
            )

            # Create the collaboration result checking tool (handles standalone mode internally)
            collaboration_result_tool = create_check_collaboration_result_tool(
                self.communication_hub, self.agent_registry, self._current_agent_id
            )

            if self._is_standalone_mode:
                logger.debug(
                    f"Registered standalone mode collaboration tools for agent: {self._current_agent_id}"
                )
            else:
                logger.debug(
                    f"Registered connected mode collaboration tools for agent: {self._current_agent_id}"
                )

            # Register the tools
            self._tool_registry.register_tool(agent_search_tool)
            self._tool_registry.register_tool(collaboration_request_tool)
            self._tool_registry.register_tool(collaboration_result_tool)

            self._agent_specific_tools_registered = True

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
        return create_agent_search_tool(
            self.agent_registry, self._current_agent_id, self.communication_hub
        )

    def create_send_collaboration_request_tool(self) -> StructuredTool:
        """Create a tool for sending collaboration requests to other agents."""
        return create_send_collaboration_request_tool(
            self.communication_hub, self.agent_registry, self._current_agent_id
        )

    def create_check_collaboration_result_tool(self) -> StructuredTool:
        """Create a tool for checking the status of sent collaboration requests."""
        return create_check_collaboration_result_tool(
            self.communication_hub, self.agent_registry, self._current_agent_id
        )

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
        # Delegate to the implementation in custom_tools
        return create_task_decomposition_tool(self.llm)

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

    @property
    def is_standalone_mode(self) -> bool:
        """
        Check if the PromptTools instance is running in standalone mode.

        Returns:
            True if running in standalone mode (without registry/hub),
            False if running in connected mode (with registry/hub)
        """
        return self._is_standalone_mode
