# AgentConnect Examples

This directory contains examples demonstrating how to use the AgentConnect framework. These examples are organized by functionality to help you understand different aspects of the framework.

## Directory Structure

- `agents/`: Examples demonstrating how to create and use different types of agents
- `communication/`: Examples showing how agents communicate with each other
- `multi_agent/`: Examples of multi-agent systems and collaborative workflows

## Running Examples

To run these examples, you'll need to have AgentConnect installed:

```bash
# Install AgentConnect with demo dependencies
poetry install
```

### Recommended Method: Using the CLI Tool

The recommended way to run examples is using the CLI tool that's installed with the package:

```bash
# Run a specific example
agentconnect --example chat
agentconnect --example multi
agentconnect --example research
agentconnect --example data
agentconnect --example telegram

# Run with detailed logging
agentconnect --example telegram --verbose
```

### Alternative Method: Running Python Scripts Directly

Each example can also be run directly as a Python script:

```bash
# Run a specific example
python examples/agents/basic_agent_usage.py

# Run a communication example
python examples/communication/basic_communication.py

# Run the modular multi-agent system
python examples/multi_agent/multi_agent_system.py
```

## Available Examples

### Agent Examples

- `basic_agent_usage.py`: Demonstrates how to create and use a basic AI agent

### Communication Examples

- `basic_communication.py`: Shows how to set up communication between agents

### Multi-Agent Examples

- `multi_agent/`: A complete modular multi-agent system with the following components:
  - `multi_agent_system.py`: Main orchestration script
  - `telegram_agent.py`: Agent for Telegram bot integration
  - `research_agent.py`: Agent for web search and information retrieval
  - `content_processing_agent.py`: Agent for document processing and formatting
  - `data_analysis_agent.py`: Agent for data analysis and visualization
  - `message_logger.py`: Utility for visualizing agent interactions

## Creating Your Own Examples

Feel free to create your own examples based on these templates. If you create an example that might be useful to others, consider contributing it back to the project!

## Notes

- These examples are designed to be simple and focused on specific features
- For more complex use cases, see the documentation
- API keys for AI providers should be set in your environment variables (see `.env.example`)

## Prerequisites

Before running these examples, make sure you have:

1. Set up your environment variables in a `.env` file in the project root with your API keys:
   ```
   # Provider API Keys (at least one is required)
   OPENAI_API_KEY=your_openai_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   GROQ_API_KEY=your_groq_api_key

   # Optional: LangSmith for monitoring (recommended)
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
   LANGSMITH_API_KEY=your_langsmith_api_key
   LANGSMITH_PROJECT=AgentConnect
   ```

2. Installed all required dependencies:
   ```bash
   poetry install

   # For research capabilities in the multi-agent system
   poetry install --with research
   ```

## Available Examples

The following examples are available through the CLI tool (`agentconnect --example <name>`):

### 1. Chat Example (chat)

Demonstrates a simple chat interface with a single AI agent:
- A human user interacts with an AI assistant
- The assistant responds to user queries in real-time
- Supports multiple AI providers (OpenAI, Anthropic, Groq, Google)

**Key Features:**
- Human-to-agent interaction
- Real-time chat interface
- Multiple provider/model selection
- Message history tracking
- Simple command-line interface

### 2. Multi-Agent Analysis (multi)

Demonstrates autonomous interaction between specialized AI agents:
- A data processor agent analyzes e-commerce data
- A business analyst agent provides strategic insights
- Agents collaborate without human intervention

**Key Features:**
- Agent-to-agent communication
- Autonomous collaboration
- Structured data analysis
- Real-time conversation visualization
- Capability-based interaction

### 3. Research Assistant (research)

Demonstrates a research workflow with multiple specialized AI agents:
- A human user interacts with a research coordinator agent
- The coordinator delegates tasks to specialized agents:
  - Research Agent: Finds information on a topic
  - Summarization Agent: Condenses and organizes information
  - Fact-Checking Agent: Verifies the accuracy of information

**Key Features:**
- Multi-agent collaboration
- Task decomposition and delegation
- Human-in-the-loop interaction
- Capability-based agent discovery
- Asynchronous message processing

### 4. Data Analysis Assistant (data)

Demonstrates a data analysis workflow with specialized agents:
- A human user interacts with a data analysis coordinator
- The coordinator works with specialized agents:
  - Data Processor: Cleans and prepares data
  - Statistical Analyst: Performs statistical analysis
  - Visualization Expert: Creates data visualizations
  - Insights Generator: Extracts business insights

**Key Features:**
- Data-focused agent capabilities
- Multi-step analysis workflow
- Visualization generation
- Insight extraction
- Human-in-the-loop guidance

### 5. Modular Multi-Agent System (telegram)

Demonstrates a modular approach to building a multi-agent system with Telegram integration:
- Each agent is implemented in its own file for clean separation of concerns
- Users can interact with agents through both Telegram and CLI
- The system includes specialized agents for different tasks:
  - Telegram Agent: Handles Telegram messaging platform integration
  - Research Agent: Performs web searches and information retrieval
  - Content Processing Agent: Handles document processing and format conversion
  - Data Analysis Agent: Analyzes data and creates visualizations

**Key Features:**
- Modular design with separate agent implementations
- Factory pattern for agent creation
- Message flow visualization
- Telegram integration
- CLI interface for direct interaction
- Web search capabilities
- Data analysis and visualization
- Asynchronous message processing
- Publishing capabilities

**Prerequisites for the Multi-Agent System:**
- Python 3.11 or higher
- For Telegram functionality: A Telegram bot token (create one through [@BotFather](https://t.me/botfather))
- API keys for one of the supported LLM providers (Google, OpenAI, Anthropic, or Groq)
- Optional: Tavily API key for improved web search capabilities
- The `arxiv` and `wikipedia` packages for the research agent (install with `poetry install --with research`)

**Setting Up the Multi-Agent System:**
1. Create a `.env` file with:
   ```
   # Required - at least one of these LLM API keys
   GOOGLE_API_KEY=your_google_api_key
   # OR
   OPENAI_API_KEY=your_openai_api_key
   # OR
   ANTHROPIC_API_KEY=your_anthropic_api_key
   # OR
   GROQ_API_KEY=your_groq_api_key

   # Optional for Telegram integration
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token

   # Optional for improved research capabilities
   TAVILY_API_KEY=your_tavily_api_key
   ```

2. Install the required dependencies:
   ```bash
   # Core dependencies
   poetry install

   # Research agent dependencies
   poetry install --with research
   ```

3. Run the system:
   ```bash
   # Using the CLI tool (recommended)
   agentconnect --example telegram
   
   # For detailed logging, add the --verbose flag:
   agentconnect --example telegram --verbose
   
   # Alternative: run the Python script directly
   python examples/multi_agent/multi_agent_system.py
   python examples/multi_agent/multi_agent_system.py --logging
   ```

4. If the Telegram bot token is provided, you can interact with the bot on Telegram:
   - Use `/start` to initialize the bot
   - Use `/help` to get help information
   - Ask questions or request research, content processing, or data analysis
   - Publish

For more details on the implementation, see the source code and comments in the `multi_agent/` directory.

## Monitoring with LangSmith

These examples integrate with LangSmith for monitoring and debugging agent workflows:

1. **View Agent Traces**: Each example generates traces in LangSmith that you can view to understand agent behavior
2. **Debug Issues**: Identify and fix problems in agent workflows
3. **Analyze Performance**: Measure response times and token usage

To enable LangSmith monitoring, make sure to set the following environment variables:

```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=AgentConnect
```

## Customizing Examples

You can customize these examples by:

1. Modifying the agent capabilities in the `setup_agents()` function
2. Changing the agent personalities and behaviors
3. Adding new specialized agents with different capabilities
4. Adjusting the interaction flow between agents
5. Configuring different LLM providers and models

## Agent Processing Loops

Each example initializes the agent processing loops using `asyncio.create_task()` after registering the agents with the communication hub. These processing loops allow the agents to autonomously:

1. Listen for incoming messages
2. Process messages using their workflows
3. Send responses to other agents
4. Execute their capabilities

The processing loops are properly cleaned up when the examples finish running, ensuring that all resources are released.

```python
# Example of starting agent processing loops
asyncio.create_task(agent.run())

# Example of cleaning up agent processing tasks
if hasattr(agent, "_processing_task") and agent._processing_task:
    agent._processing_task.cancel()
```

## Troubleshooting

If you encounter issues:

1. Check that your API keys are correctly set in the `.env` file
2. Ensure all dependencies are installed
3. Check the logs for detailed error messages (each example has logging enabled by default)
4. Make sure you're running the examples from the project root directory
5. View the LangSmith traces to identify where issues occur
