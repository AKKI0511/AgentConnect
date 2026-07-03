# Multi-Agent System Examples

This directory contains examples demonstrating how to create and use multi-agent systems with the AgentConnect framework.

## Available Agents

- **Telegram Agent** (`telegram_agent.py`): Handles Telegram messaging platform interactions
- **Research Agent** (`research_agent.py`): Performs web searches and information retrieval
- **Content Processing Agent** (`content_processing_agent.py`): Handles document processing and format conversion
- **Data Analysis Agent** (`data_analysis_agent.py`): Analyzes data and creates visualizations

## Key Implementation Patterns

- **Modular design**: Each agent is defined in its own file with a factory function
- **AgentProfile-based**: All agents use the recommended AgentProfile approach
- **Factory functions**: Each agent is created through a factory function
- **Message-based communication**: Agents communicate through the hub
- **Proper lifecycle management**: Agents implement run() and stop() methods

### Agent Creation Pattern

Each agent follows this implementation pattern:

```python
def create_agent_name(provider_type: ModelProvider, model_name: ModelName, api_key: str) -> AIAgent:
    # 1. Create identity
    agent_identity = AgentIdentity.create_key_based()
    
    # 2. Define capabilities and skills
    agent_capabilities = [...]
    agent_skills = [...]
    
    # 3. Create agent profile
    agent_profile = AgentProfile(
        agent_id="agent_id",
        agent_type=AgentType.AI,
        name="Agent Name",
        summary="Brief description",
        description="Detailed description",
        capabilities=agent_capabilities,
        skills=agent_skills,
        # Other profile fields...
    )
    
    # 4. Define custom tools (if needed)
    agent_tools = [...]
    
    # 5. Create and return agent instance
    agent = AIAgent(
        agent_id="agent_id",
        identity=agent_identity,
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        profile=agent_profile,
        personality="Agent's personality used in system prompt",
        custom_tools=agent_tools,
    )
    
    return agent
```


## Running Examples

```bash
# Install core + research dependencies
poetry install --with research

# Run the multi-agent system
python examples/multi_agent/multi_agent_system.py

# Run with detailed logging
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

## Best Practices

1. **Separate description from personality**: 
   - `description` in AgentProfile is discoverable by other agents
   - `personality` is used in system prompts

2. **Implement with AgentProfile**: Use the AgentProfile pattern for consistent initialization

3. **Implement proper lifecycle management**: Use run() and stop() methods

For detailed implementation guides, best practices, and advanced topics, see the [AgentConnect Documentation](https://akki0511.github.io/AgentConnect/guides/index.html).