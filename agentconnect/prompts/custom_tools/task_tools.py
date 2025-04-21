"""
Task-related tools for agent workflows.

This module provides tools for task decomposition and management within the AgentConnect framework.
These tools help agents break down complex tasks into manageable subtasks.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, TypeVar

from langchain.tools import StructuredTool
from langchain.llms.base import BaseLLM
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Type variable for better type hinting
T = TypeVar("T", bound=BaseModel)


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


async def _fallback_task_decomposition(
    task_description: str, max_subtasks: int = 5, subtasks_text: str = None
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


def create_task_decomposition_tool(llm: Optional[BaseLLM] = None) -> StructuredTool:
    """
    Create a tool for decomposing complex tasks into subtasks.

    Args:
        llm: Optional language model for advanced task decomposition

    Returns:
        A StructuredTool for task decomposition that can be used in agent workflows
    """

    # Synchronous implementation
    def decompose_task(task_description: str, max_subtasks: int = 5) -> Dict[str, Any]:
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
        """
        # Create the output parser
        parser = JsonOutputParser(pydantic_object=TaskDecompositionResult)

        # Create the system prompt with optimized structure
        system_prompt = f"""TASK: {task_description}
MAX SUBTASKS: {max_subtasks}

INSTRUCTIONS:
1. Analyze complexity
2. Break into clear subtasks
3. Each subtask: 1-2 sentences only
4. Include dependencies if needed
5. Format as structured list

{parser.get_format_instructions()}

Each subtask needs: ID, title, description.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Decompose: {task_description}"),
        ]

        try:
            # Use the LLM to decompose the task
            if llm:
                # Use the LLM with structured output
                response = await llm.ainvoke(messages)

                try:
                    # Try to parse the response as JSON
                    result = parser.parse(response.content)
                    return result
                except Exception as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {str(e)}")
                    # Fall back to manual parsing if JSON parsing fails
                    return await _fallback_task_decomposition(
                        task_description, max_subtasks, response.content
                    )
            else:
                # Fallback to a simple decomposition
                return await _fallback_task_decomposition(
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

    # Create and return the tool
    tool = StructuredTool.from_function(
        func=decompose_task,
        name="decompose_task",
        description="Breaks down a complex task into smaller, manageable subtasks. Use this when faced with a multi-step or complex request.",
        args_schema=TaskDecompositionInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=decompose_task_async,
    )
    tool.metadata = tool.metadata or {}
    tool.metadata["category"] = "task_management"
    return tool
