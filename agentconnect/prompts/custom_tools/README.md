# Custom Tools Directory

This directory contains modular implementations of tools used by agents in the AgentConnect framework. The tools are organized by category and purpose, with each file containing related tool functionality.

## Directory Structure

```
custom_tools/
├── registry.py                # Tool registry for managing available tools
├── collaboration_tools.py     # Agent search and collaboration request tools
├── task_tools.py              # Task decomposition and management tools
└── README.md                  # This documentation file
```

## Purpose

The custom_tools directory serves several important purposes:

1. **Modular Organization**: Keep related tool implementations together while separating different tool categories
2. **Code Separation**: Reduce the size and complexity of the main tools.py file
3. **Scalability**: Make it easier to add new tools without cluttering the main tools file
4. **Maintainability**: Improve code organization and readability
5. **Reusability**: Enable tool implementations to be reused across different parts of the framework

## Tool Implementation Pattern

Each tool implementation should follow a consistent pattern:

1. **Define Input/Output Schemas**: Use Pydantic models to define input and output schemas for the tool
2. **Implement Both Sync and Async Versions**: Provide both synchronous and asynchronous implementations 
3. **Create Factory Function**: Provide a function that creates and returns a StructuredTool instance
4. **Provide Proper Documentation**: Document the purpose, parameters, and return values of each tool

### Example Structure

```python
"""
Module docstring explaining the purpose of these tools.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

# Define input/output schemas
class MyToolInput(BaseModel):
    """Input schema for my tool."""
    param1: str = Field(description="Description of parameter 1")
    param2: int = Field(10, description="Description of parameter 2 with default value")

class MyToolOutput(BaseModel):
    """Output schema for my tool."""
    result: str = Field(description="Description of the result")
    success: bool = Field(description="Whether the operation was successful")

# Create the tool factory function
def create_my_tool(dependency1, dependency2) -> StructuredTool:
    """
    Create a tool for doing something useful.
    
    Args:
        dependency1: First dependency needed by the tool
        dependency2: Second dependency needed by the tool
        
    Returns:
        A StructuredTool for performing some action
    """
    # Synchronous implementation
    def my_tool_sync(param1: str, param2: int = 10) -> Dict[str, Any]:
        """Synchronous implementation of the tool."""
        try:
            # Implementation details...
            return {"result": "some result", "success": True}
        except Exception as e:
            # Error handling...
            return {"result": f"Error: {str(e)}", "success": False}
    
    # Asynchronous implementation
    async def my_tool_async(param1: str, param2: int = 10) -> Dict[str, Any]:
        """Asynchronous implementation of the tool."""
        try:
            # Implementation details...
            # Use async/await for I/O-bound operations
            return {"result": "some result", "success": True}
        except Exception as e:
            # Error handling...
            return {"result": f"Error: {str(e)}", "success": False}
    
    # Create and return the tool
    return StructuredTool.from_function(
        func=my_tool_sync,
        name="my_tool",
        description="Description of what this tool does and when to use it",
        args_schema=MyToolInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=my_tool_async,
    )
```

## Adding New Tools

To add a new tool or category of tools:

1. **Create a New File**: If your tool doesn't fit well with existing categories, create a new file
2. **Define Schemas**: Create Pydantic models for input/output validation
3. **Implement Logic**: Follow the tool implementation pattern above
4. **Update tools.py**: Import and expose your tool in the main tools.py file
5. **Update Documentation**: Update the README files to document your new tool

### In tools.py

After creating your new tool implementation, you need to expose it in tools.py:

```python
# In tools.py
from agentconnect.prompts.custom_tools.your_new_file import (
    YourToolInput,
    YourToolOutput,
    create_your_tool
)

class PromptTools:
    # ...existing code...
    
    def create_your_tool(self) -> StructuredTool:
        """Create a tool for your specific purpose."""
        # Delegate to the implementation in custom_tools
        return create_your_tool(
            self.dependency1,
            self.dependency2,
            self._current_agent_id
        )
        
    def _register_basic_tools(self) -> None:
        # ...existing code...
        # Register your new tool if it doesn't require an agent ID
        your_tool = create_your_tool(self.dependency1, self.dependency2)
        self._tool_registry.register_tool(your_tool)
```

## Best Practices

### Tool Design

1. **Single Responsibility**: Each tool should do one thing and do it well
2. **Clear Documentation**: Document the purpose, inputs, outputs, and usage clearly
3. **Error Handling**: Implement robust error handling in both sync and async versions
4. **Logging**: Use logging to provide visibility into tool operation
5. **Timeouts**: Implement timeouts for external operations
6. **Dependency Injection**: Pass dependencies to the tool factory function rather than importing them directly

### Code Quality

1. **Type Hints**: Use proper type hints for better code documentation and IDE support
2. **Consistent Naming**: Follow consistent naming patterns
3. **Test Coverage**: Write unit tests for your tools
4. **Clean Code**: Keep implementations clean, readable, and well-organized
5. **Documentation**: Document all public functions and classes

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure proper imports in tools.py when adding new tools
2. **Event Loop Issues**: Handle event loop management properly for async operations
3. **Missing Dependencies**: Ensure all dependencies are available at runtime

### Debugging Tools

To debug a tool implementation:

1. **Enable DEBUG Logging**: Set logging level to DEBUG to see detailed operation
2. **Add Tracing**: Add logging at key points in the implementation
3. **Test Isolation**: Test the tool in isolation before integrating with the agent system 