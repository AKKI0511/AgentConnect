# Utils Module

The utils module provides utility functions and classes used throughout the AgentConnect framework, including interaction control for rate limiting, token usage tracking, and logging configuration.

## Structure

```
utils/
├── __init__.py           # Package initialization and API exports
├── interaction_control.py # Rate limiting and interaction tracking
├── logging_config.py     # Logging configuration
├── payment_helper.py     # Payment utilities for CDP validation and agent payment readiness
├── wallet_manager.py     # Agent wallet persistence utilities
└── README.md             # This file
```

## Key Components

### Interaction Control (`interaction_control.py`)

The interaction control system provides rate limiting and interaction tracking for agents:

- **Token-based Rate Limiting**: Configurable limits per minute and hour
- **Automatic Cooldown**: When limits are reached, agents enter a cooldown period
- **Turn Tracking**: Track and limit the number of turns in a conversation
- **Conversation Statistics**: Track token usage and turn counts per conversation
- **LangChain Integration**: Provides callbacks for LangChain and LangGraph

Key classes:
- `InteractionControl`: High-level control for agent interactions
- `TokenConfig`: Configuration for token-based rate limiting
- `InteractionState`: Enum for interaction states (CONTINUE, STOP, WAIT)
- `RateLimitingCallbackHandler`: LangChain callback handler for rate limiting

### Logging Configuration (`logging_config.py`)

The logging configuration system provides a consistent logging setup across the framework:

- **Colored Output**: Different colors for different log levels
- **Module-specific Levels**: Configure log levels for specific modules
- **LangGraph Integration**: Special setup for LangGraph components

Key classes and functions:
- `setup_logging()`: Configure logging with colors and per-module settings
- `LogLevel`: Enum for log levels (DEBUG, INFO, WARNING, ERROR)
- `ColoredFormatter`: Custom formatter with colors for log messages
- `disable_all_logging()`: Disable all logging output
- `get_module_levels_for_development()`: Get recommended log levels for development
- `setup_langgraph_logging()`: Configure logging specifically for LangGraph components

### Payment Helper (`payment_helper.py`)

The payment helper module provides utility functions for setting up and managing payment capabilities:

- **CDP Environment Validation**: Verify CDP API keys and required packages
- **Agent Payment Readiness**: Check if an agent is ready for payments
- **Wallet Metadata Retrieval**: Get metadata about agent wallets
- **Backup Utilities**: Create backups of wallet data

Key functions:
- `verify_payment_environment()`: Check required environment variables
- `validate_cdp_environment()`: Validate the entire CDP setup including packages
- `check_agent_payment_readiness()`: Check if an agent can make payments
- `backup_wallet_data()`: Create backup of wallet data

### Wallet Manager (`wallet_manager.py`)

The wallet manager provides wallet data persistence for agents:

- **Wallet Data Storage**: Save and load wallet data securely
- **Wallet Existence Checking**: Check if wallet data exists
- **Wallet Data Management**: Delete and backup wallet data
- **Configuration Management**: Set custom data directories

Key functions:
- `save_wallet_data()`: Persist wallet data for an agent
- `load_wallet_data()`: Load wallet data for an agent
- `wallet_exists()`: Check if wallet data exists
- `get_all_wallets()`: List all wallet files
- `delete_wallet_data()`: Delete wallet data

## Usage Examples

### Interaction Control

```python
from agentconnect.utils import InteractionControl, TokenConfig, InteractionState

# Create token config
token_config = TokenConfig(
    max_tokens_per_minute=5500,
    max_tokens_per_hour=100000
)

# Create interaction control
interaction_control = InteractionControl(token_config=token_config)

# Set cooldown callback
interaction_control.set_cooldown_callback(
    lambda duration: print(f"Cooldown for {duration} seconds")
)

# Get callback manager for LangChain/LangGraph
callbacks = interaction_control.get_callback_manager()

# Use in LangGraph workflow
config = {
    "configurable": {"thread_id": "conversation_id"},
    "callbacks": callbacks
}
result = await workflow.ainvoke(initial_state, config)

# Process interaction after response
state = await interaction_control.process_interaction(
    token_count=1500,
    conversation_id="conversation_123"
)

# Check the state
if state == InteractionState.CONTINUE:
    print("Continuing conversation")
elif state == InteractionState.STOP:
    print("Maximum turns reached, stopping conversation")
elif state == InteractionState.WAIT:
    print("Rate limit reached, waiting for cooldown")

# Get conversation statistics
stats = interaction_control.get_conversation_stats("conversation_123")
print(f"Total tokens: {stats['total_tokens']}")
print(f"Turn count: {stats['turn_count']}")
```

### Logging Configuration

```python
from agentconnect.utils import setup_logging, LogLevel, disable_all_logging

# Basic setup
setup_logging(level=LogLevel.INFO)

# Module-specific levels
setup_logging(
    level=LogLevel.INFO,
    module_levels={
        "agentconnect.agents.ai_agent": LogLevel.DEBUG,
        "langchain": LogLevel.WARNING
    }
)

# Get recommended log levels for development
from agentconnect.utils import get_module_levels_for_development
module_levels = get_module_levels_for_development()
setup_logging(level=LogLevel.INFO, module_levels=module_levels)

# LangGraph-specific setup
from agentconnect.utils import setup_langgraph_logging
setup_langgraph_logging(level=LogLevel.INFO)

# Disable all logging for examples
disable_all_logging()
```

### Payment Utilities

```python
from agentconnect.utils import payment_helper, wallet_manager

# Validate CDP environment
is_valid, message = payment_helper.validate_cdp_environment()
if not is_valid:
    print(f"CDP environment is not properly configured: {message}")
    # Set up environment...

# Check agent payment readiness
status = payment_helper.check_agent_payment_readiness(agent)
if status["ready"]:
    print(f"Agent is ready for payments with address: {status['payment_address']}")
else:
    print(f"Agent is not ready for payments: {status}")

# Save wallet data
wallet_manager.save_wallet_data(
    agent_id="agent123",
    wallet_data=agent.wallet_provider.export_wallet(),
    data_dir="custom/wallet/dir"  # Optional
)

# Load wallet data
wallet_json = wallet_manager.load_wallet_data("agent123")
if wallet_json:
    print("Wallet data loaded successfully")

# Back up wallet data
backup_path = payment_helper.backup_wallet_data(
    agent_id="agent123",
    backup_dir="wallet_backups"
)
print(f"Wallet backed up to: {backup_path}")
```

## Wallet Security Note

IMPORTANT: The default wallet data storage implementation in `wallet_manager.py` stores wallet data unencrypted on disk, which is suitable for testing/demo purposes but NOT secure for production environments holding real assets. For production use, implement proper encryption or use a secure key management system.

## Integration with LangGraph

The rate limiting system is designed to work seamlessly with LangGraph:

1. **Callback Propagation**: Callbacks are passed through the entire workflow
2. **Token Usage Tracking**: Token usage is tracked at the LLM level
3. **Automatic Cooldown**: When rate limits are reached, the agent enters cooldown

### Best Practices

1. **Always use the callback manager**: Always pass the callback manager to workflow invocations
2. **Set a cooldown callback**: Set a callback to handle cooldown periods
3. **Process interactions**: Always call `process_interaction` after receiving a response
4. **Monitor token usage**: Use logging to monitor token usage and detect rate limiting issues
5. **Configure appropriate limits**: Set appropriate token limits based on your API provider's rate limits

## Troubleshooting

If you encounter rate limiting issues:

1. **Check logs**: Look for warnings about rate limits being reached
2. **Increase limits**: If necessary, increase the token limits in your configuration
3. **Implement backoff**: Consider implementing exponential backoff for retries
4. **Monitor usage patterns**: Analyze usage patterns to identify potential optimizations
