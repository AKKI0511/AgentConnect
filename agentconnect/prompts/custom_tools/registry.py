"""
Registry for all available tools that can be used by agents.

This module provides a centralized registry for managing the tools available to agents,
allowing for registering, retrieving, and categorizing tools.
"""

from typing import Dict, List, Optional

from langchain.tools import StructuredTool


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
