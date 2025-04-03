# Multi-Agent Examples

This directory contains examples demonstrating how to create and use multi-agent systems in the AgentConnect framework.

## Available Examples

### Modular Multi-Agent System

A complete example of a modular multi-agent system with:
- Separate agent implementations in individual files
- Inter-agent communication and collaboration
- CLI interface for direct interaction with agents
- Telegram bot integration

The system includes these specialized agents:
1. **Telegram Agent** (`telegram_agent.py`): Handles Telegram messaging platform interactions
2. **Research Agent** (`research_agent.py`): Performs web searches and information retrieval
3. **Content Processing Agent** (`content_processing_agent.py`): Handles document processing and format conversion
4. **Data Analysis Agent** (`data_analysis_agent.py`): Analyzes data and creates visualizations

## Architecture

The multi-agent system architecture follows these principles:
- **Modular design**: Each agent is implemented in its own file for clean separation of concerns
- **Factory pattern**: Agents are created through factory functions for easy configuration
- **Dependency injection**: Resources like the registry and hub are injected where needed
- **Message flow visualization**: Agent interactions are visualized in the terminal
- **CLI interface**: Direct interaction with agents through a command-line interface

## Running Examples

To run the multi-agent system:

```bash
# Install core dependencies
poetry install

# Install research dependencies (required for Research Agent)
poetry install --with research

# Run the multi-agent system
python examples/multi_agent/multi_agent_system.py

# Run with detailed logging enabled
python examples/multi_agent/multi_agent_system.py --logging
```

## Required Environment Variables

Set these in your `.env` file:

```
# Required for LLM functionality (at least one needed)
GOOGLE_API_KEY=your_google_api_key
# Or any of these alternatives:
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GROQ_API_KEY=your_groq_api_key

# Required for Telegram agent (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Optional for enhanced research capabilities
TAVILY_API_KEY=your_tavily_api_key
```

## Required Packages

The multi-agent system requires specific packages for each agent to function properly:

```bash
# Research Agent dependencies
poetry install --with research    # Installs arxiv and wikipedia packages

# Data Analysis Agent dependencies are included in the main dependencies

# Content Processing Agent dependencies are included in the main dependencies

# Telegram Agent dependencies are included with the main or demo dependencies
```

You can also install all dependencies for development and examples in one command:

```bash
# Install everything needed for development and all examples
poetry install --with demo,research,dev
```

## Creating Your Own Multi-Agent Examples

When creating your own multi-agent examples, consider:

1. **Agent Roles**: Define clear roles and responsibilities for each agent
2. **Coordination Mechanisms**: Implement mechanisms for agent coordination
3. **Task Decomposition**: Show how to break down complex tasks
4. **Conflict Resolution**: Demonstrate how to handle conflicting agent goals or actions
