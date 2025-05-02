# Prompts Module

The prompts module serves as the "brain" of the AgentConnect framework, providing core logic for agent workflows, tools for collaboration, and prompt templates that guide agent behavior.

## Structure

```
prompts/
├── __init__.py           # Module initialization and exports
├── agent_prompts.py      # Core workflow definitions for different agent types
├── chain_factory.py      # Factory functions for creating LangGraph workflows
├── tools.py              # Tool delegation and framework (delegates to custom_tools)
├── custom_tools/         # Modular tool implementations
│   ├── registry.py       # Tool registry for managing available tools
│   ├── collaboration_tools.py # Agent search and collaboration request tools
│   └── task_tools.py     # Task decomposition and management tools
├── templates/            # Prompt templates directory
│   └── prompt_templates.py  # Templates for system prompts, collaboration, etc.
└── README.md             # This documentation file
```

## Key Components

### Workflows (`agent_prompts.py`)

The workflow system is the core of the prompt architecture. It uses LangGraph to create stateful, multi-step workflows that can persist conversation state between invocations.

### Key Workflows

- **`AIAgentWorkflow`**: Main workflow for AI agents, handling general conversation and collaboration decisions.
- **`TaskDecompositionWorkflow`**: Workflow for breaking down complex tasks into subtasks.
- **`CollaborationRequestWorkflow`**: Workflow for handling collaboration requests from other agents.

### Workflow Structure

Each workflow consists of three main nodes:

1. **Preprocess**: Prepares the state before the ReAct agent runs, handling context management and state initialization.
2. **React**: Runs the ReAct agent, which makes decisions and calls tools as needed.
3. **Postprocess**: Processes the results of the ReAct agent, extracting tool results and handling topic changes.

### Memory Management

Workflows use LangGraph's built-in persistence features for agent conversations:

- **`MemorySaver`**: LangGraph's built-in checkpointer for persisting conversation state.
- **`thread_id`**: Unique identifier for each conversation, used to maintain conversation context.

#### Conversation Isolation

Each agent-to-agent conversation has its own isolated memory context through unique thread_ids. This ensures:
1. No data leakage between conversations
2. Reduced token usage by only loading relevant conversation history
3. Better security and privacy for sensitive information

#### Context Management

The workflow system includes sophisticated context management features:
- **Context Reset**: Automatically resets the context when there's a long gap between interactions (over 30 minutes)
- **Topic Change Detection**: Uses TF-IDF vectorization and cosine similarity to detect when the conversation topic changes
- **Selective Memory Retention**: Keeps only relevant messages when context is reset or topic changes

## Tools System

The tools system provides agents with the ability to perform specific actions, particularly related to collaboration and task management.

### Key Tools

- **`search_for_agents`**: Searches for agents with specific capabilities using semantic matching. This tool helps agents find other specialized agents that can assist with tasks outside their capabilities.
- **`send_collaboration_request`**: Sends a request to a specific agent to perform a task and waits for a response. This tool enables agent-to-agent delegation and collaboration.
- **`decompose_task`**: Breaks down a complex task into smaller, manageable subtasks. This helps agents organize and tackle complex requests more effectively.
- **AgentKit Payment Tools (e.g., `native_transfer`, `erc20_transfer`)**: When payment capabilities are enabled for an `AIAgent`, tools provided by Coinbase AgentKit are automatically added. These allow the agent to initiate and manage cryptocurrency transactions based on LLM decisions guided by payment prompts.

### Tool Architecture

The tools system uses a modular architecture with a clean separation of concerns:

- **`tools.py`**: Main entry point that:
  - Defines the `PromptTools` class which manages tool creation and registration
  - Delegates implementation details to specialized modules in the `custom_tools` directory
  - Maintains backward compatibility with existing code

- **`custom_tools/`**: Directory containing modular tool implementations:
  - **`registry.py`**: Contains the `ToolRegistry` class for managing available tools
  - **`collaboration_tools.py`**: Implementations for agent search and collaboration request tools
  - **`task_tools.py`**: Implementations for task decomposition and management tools

- **`PromptTools`**: Main class for creating and managing tools for agents:
  - Handles tool creation, registration, and retrieval
  - Maintains agent context for tools that need it
  - Delegates actual implementation to specialized modules while maintaining consistent APIs

- **`ToolRegistry`**: Central registry for managing available tools:
  - Each agent has its own isolated registry
  - Tools can be categorized (e.g., 'collaboration', 'task_management')
  - Supports tool lookup by name or category

### Extending the Tool System

The modular architecture makes it easy to add new tools:

1. Create a new file in the `custom_tools` directory (e.g., `search_tools.py`)
2. Define your tool's input/output schemas and implementation functions
3. Import and expose these functions in `tools.py`

This approach ensures:
- Better code organization and maintenance
- Easier testing of individual tool components
- Cleaner separation of concerns
- Simplified development of new tools

```python
# Example: Adding a new tool in custom_tools/search_tools.py
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
import asyncio

# Define input schema
class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    
# Create the tool function
def create_web_search_tool():
    def search(query: str):
        # Synchronous implementation
        # ...
    
    async def search_async(query: str):
        # Asynchronous implementation
        # ...
    
    return StructuredTool.from_function(
        func=search,
        name="web_search",
        description="Search the web for information",
        args_schema=WebSearchInput,
        coroutine=search_async
    )

# Then in tools.py, import and expose:
from agentconnect.prompts.custom_tools.search_tools import create_web_search_tool
```

### Tool Creation

Tools are created using the `PromptTools` class, which provides methods for creating and managing tools:

```python
# Creating a custom tool
tool = prompt_tools.create_tool_from_function(
    func=my_function,               # Synchronous implementation
    coroutine=my_async_function,    # Asynchronous implementation (optional)
    name="my_custom_tool",
    description="Tool description shown to the agent",
    args_schema=MyArgsSchema,       # Pydantic model for validation
    category="custom_tools"         # Category for organization
)
```

### Tool Usage in Workflows

When an agent needs to use tools, it requests them from the `PromptTools` instance:

```python
# Get all collaboration tools for an agent
collaboration_tools = prompt_tools.get_tools_for_workflow(
    categories=["collaboration"],
    agent_id="agent_123"  # For logging purposes
)

# Register a specific agent as the current user of the tools
prompt_tools.set_current_agent("agent_123")
```

### Tool Implementation Details

Each tool follows a consistent pattern:
- Both synchronous and asynchronous implementations
- Proper error handling and logging
- Clear input/output schemas using Pydantic models
- Comprehensive metadata for discoverability

### Security and Safety Features

The tools system includes several security features:
- **Collaboration Chain Tracking**: Prevents infinite loops in agent collaboration
- **Timeouts**: All external requests have configurable timeouts
- **Error Handling**: Graceful degradation when tools encounter errors
- **Permission Checks**: Tools verify that agents have appropriate permissions

## Prompt Templates

Prompt templates are used to create different types of prompts for agents. The `PromptTemplates` class provides methods for creating various types of prompts:

- **System Prompts**: Define the agent's role, capabilities, and personality.
- **Collaboration Prompts**: Used for collaboration requests and responses.
- **ReAct Prompts**: Used for the ReAct agent, which makes decisions and calls tools. This includes the `CORE_DECISION_LOGIC` template, which incorporates instructions for when to consider collaboration or payments.
- **Payment Capability Prompts**: Includes the `PAYMENT_CAPABILITY_TEMPLATE`, which provides specific instructions and context to the LLM regarding the available payment tools and when it might be appropriate to use them for agent-to-agent transactions.

### ReAct Integration

The system uses LangGraph's prebuilt ReAct agent, which follows the Reasoning and Acting pattern:
- **Reasoning**: The agent reasons about the current state and decides what to do next
- **Acting**: The agent takes actions by calling tools
- **Observation**: The agent observes the results of its actions and updates its reasoning

## Integration with AIAgent

The `AIAgent` class in `agentconnect/agents/ai_agent.py` uses the workflow system to process messages:

1. The agent initializes a workflow based on its type (AI, task decomposition, or collaboration request).
2. When a message is received, the agent creates an initial state with the message and invokes the workflow.
3. The workflow processes the message, making decisions and calling tools as needed.
4. The agent extracts the response from the workflow and sends it back to the sender.

### Error Handling and Resilience

The system includes robust error handling:
- **Timeout Protection**: Workflows have a configurable timeout to prevent hanging
- **Retry Mechanism**: Failed collaboration attempts can be retried automatically
- **Graceful Degradation**: If collaboration fails, the agent attempts to answer with available information

### Example Usage

```python
# Create an AI agent with a workflow
agent = AIAgent(
    agent_id="agent1",
    name="Assistant",
    provider_type=ModelProvider.OPENAI,
    model_name=ModelName.GPT4,
    api_key="your-api-key",
    identity=AgentIdentity(name="Assistant", role="assistant"),
    capabilities=[Capability(name="general", description="General assistance")],
    personality="helpful and professional",
    agent_type="ai"  # Use the AI agent workflow
)

# Process a message
response = await agent.process_message(message)
```

## Advantages Over Previous Approach

The LangGraph-based workflow system offers several advantages over the previous `chain_factory.py` approach:

1. **Stateful Workflows**: LangGraph allows for stateful workflows that can persist conversation state between invocations.
2. **Flexible Decision-Making**: Agents can make complex decisions about when to collaborate and how to process responses.
3. **Tool Integration**: Tools are seamlessly integrated into the workflow, allowing agents to perform specific actions.
4. **Memory Management**: Built-in memory management ensures that conversation context is maintained between invocations.
5. **Extensibility**: The system is designed to be extensible, allowing for the addition of new workflows, tools, and prompt templates.
6. **Better Tracing and Debugging**: LangGraph provides built-in tracing capabilities for better debugging and monitoring.
7. **Improved Performance**: The new system is more efficient, with better token usage and faster response times.

### Advantages of the Modular Tool Architecture

The refactored tool architecture offers significant advantages:

1. **Modularity**: Each type of tool lives in its own file, making the codebase easier to navigate and understand
2. **Separation of Concerns**: The `tools.py` file handles framework concerns while implementation details live in `custom_tools/`
3. **Scalability**: Easier to add new tools without cluttering the main `tools.py` file
4. **Maintainability**: Smaller, focused files are easier to test and maintain
5. **Reusability**: Tool implementations can be reused across different projects or modules

## Future Improvements

- **Advanced Memory Management**: Integration with external memory stores like Redis or PostgreSQL for better scalability.
- **More Sophisticated Topic Detection**: Improved methods for detecting topic changes in conversations.
- **Enhanced Collaboration Protocols**: More sophisticated protocols for agent-to-agent collaboration.
- **Custom Workflow Nodes**: Allow for custom workflow nodes to be added to the graph.
- **Improved Tool Discovery**: Better methods for agents to discover and use available tools.
- **Multi-Agent Collaboration**: Support for multiple agents collaborating on a single task.
- **Visualization Tools**: Tools for visualizing agent workflows and collaboration networks.
- **Additional Tool Categories**: Expand the custom_tools directory with new specialized tools (e.g., data analysis, content generation)

## Troubleshooting

### Common Issues

- **Missing Agent ID**: If tools aren't working correctly, make sure you've set the current agent ID with `set_current_agent()`.
- **Tool Timeouts**: If collaboration requests time out, check network connectivity and agent availability.
- **Memory Leaks**: For long-running applications, consider implementing periodic context resets.
- **Import Errors**: If you get import errors after adding new tools, make sure they're properly exported from their modules.

### Debugging Techniques

- Enable DEBUG level logging to see detailed tool operations
- Use LangGraph's built-in tracing capabilities
- Check collaboration chains for loops or excessive depth
- Inspect individual tool implementations in the custom_tools directory for issues
