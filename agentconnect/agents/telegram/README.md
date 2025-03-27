# Telegram Agent

The Telegram Agent module provides a Telegram bot interface for AgentConnect, allowing users to interact with an AI agent through Telegram. The implementation supports both direct Telegram user interactions and AgentConnect inter-agent collaborations.

## Architecture

The Telegram Agent implementation follows a modular architecture with clear separation of concerns:

### Core Components

- **TelegramAIAgent**: Main agent class that extends AIAgent to provide Telegram integration
- **TelegramBotManager**: Manages the Telegram bot lifecycle (initialization, polling, shutdown)
- **TelegramMessageProcessor**: Processes messages between Telegram and AgentConnect
- **HandlerRegistry**: Registry for all message handlers

### Handler Modules

- **CommandHandler**: Processes bot commands like /start, /help
- **GroupHandler**: Manages group chat interactions and mentions
- **MediaHandler**: Processes various media types (photos, documents, voice)
- **TextHandler**: Handles regular text messages

### Utility Modules

- **message_utils.py**: Message processing utilities
- **file_utils.py**: File handling utilities

### Other Components

- **keyboards.py**: Telegram keyboard layouts
- **states.py**: FSM states for multi-step interactions

## Key Features

### Messaging Capabilities

- **Private Chat**: One-on-one conversations between users and the bot
- **Group Chat**: Interaction in group chats via bot mentions
- **Media Handling**: Process photos, documents, voice messages, and other media
- **Command Processing**: Built-in commands for common operations

### Inter-Agent Collaboration

- **Capability Advertising**: Telegram-specific capabilities for discovery by other agents
- **Collaboration Handling**: Process collaboration requests from other agents
- **Announcement Broadcasting**: Send messages to all registered Telegram groups

### Dual-Purpose Processing

- **Telegram Bot Polling**: Processes messages from Telegram users
- **AgentConnect Message Queue**: Processes messages from other agents
- **Concurrent Operation**: Both processing loops run simultaneously

## Usage

### Basic Setup

```python
from agentconnect.agents.telegram import TelegramAIAgent
from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName

# Create the agent
agent = TelegramAIAgent(
    agent_id="telegram_bot",
    name="My Telegram Bot",
    provider_type=ModelProvider.GOOGLE,
    model_name=ModelName.GEMINI2_FLASH,
    api_key="your_api_key",
    identity=AgentIdentity.create_key_based(),
    telegram_token="your_telegram_token"
)

# Register with communication hub
await hub.register_agent(agent)

# Start the agent - this will start both the Telegram bot
# and the AgentConnect message processing loop
await agent.run()
```

### Environment Variables

Telegram token can be provided through environment variables:

```
TELEGRAM_BOT_TOKEN=your_telegram_token
```

### Advanced Configuration

```python
agent = TelegramAIAgent(
    agent_id="telegram_bot",
    name="My Telegram Bot",
    provider_type=ModelProvider.GOOGLE,
    model_name=ModelName.GEMINI2_FLASH,
    api_key="your_api_key",
    identity=AgentIdentity.create_key_based(),
    telegram_token="your_telegram_token",
    groups_file="custom_groups.txt",  # File to store registered group IDs
    personality="helpful and friendly",
    max_tokens_per_minute=5500,  # Rate limiting
    max_tokens_per_hour=100000,  # Rate limiting
)
```

## Integration with Other Agents

The TelegramAIAgent can collaborate with other agents through capability-based discovery:

```python
# Other agent can request collaboration
response = await my_agent.request_collaboration(
    target_agent_id="telegram_bot",
    capability_name="telegram_messaging",
    input_data={
        "message": "Announcement: Research report is ready!",
        "chat_id": "all_groups"
    }
)
```

## Directory Structure

```
telegram/
├── __init__.py            # Package initialization
├── telegram_agent.py      # Main agent implementation
├── bot_manager.py         # Telegram bot management
├── message_processor.py   # Message processing logic
├── keyboards.py           # Telegram keyboard definitions
├── states.py              # FSM state definitions
├── telegram_tools.py      # Telegram-specific tools
├── _handlers/             # Message handlers
│   ├── __init__.py
│   ├── base_handler.py
│   ├── command_handlers.py
│   ├── group_handlers.py
│   ├── media_handlers.py
│   └── text_handlers.py
└── _utils/                # Utility functions
    ├── __init__.py
    ├── file_utils.py
    └── message_utils.py
```

## Customization

You can extend the Telegram agent by:

1. Adding new handlers for custom message types
2. Extending the TelegramTools class with additional functionality
3. Customizing message processing logic in the TelegramMessageProcessor
4. Adding new capabilities to the agent

## Security Considerations

- Store the Telegram token securely (environment variables or secure storage)
- Be mindful of the permissions your bot has in group chats
- Consider implementing user authorization for sensitive operations

## Best Practices

1. **Token Management**: Use environment variables for API keys and bot tokens
2. **Error Handling**: Implement proper error handling for Telegram API operations
3. **Concurrent Processing**: Be aware of the dual processing loops (Telegram and AgentConnect)
4. **Resource Cleanup**: Ensure proper shutdown of the Telegram bot when the application exits
5. **Group Management**: Handle group registration and unregistration properly
6. **Media Management**: Clean up downloaded media files periodically 