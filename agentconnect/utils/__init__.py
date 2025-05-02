"""
Utility functions for the AgentConnect framework.

This module provides various utility functions and classes used throughout the framework,
including interaction control for rate limiting, token usage tracking, and logging configuration.

Key components:

- **InteractionControl**: Controls agent interactions with rate limiting and turn tracking
- **InteractionState**: Enum for interaction states (CONTINUE, STOP, WAIT)
- **TokenConfig**: Configuration for token-based rate limiting
- **Logging utilities**: Configurable logging setup with colored output
- **Wallet management**: Functions for handling agent wallet configurations and data
"""

# Interaction control components
from agentconnect.utils.interaction_control import (
    InteractionControl,
    InteractionState,
    RateLimitingCallbackHandler,
    TokenConfig,
)

# Logging configuration
from agentconnect.utils.logging_config import (
    LogLevel,
    disable_all_logging,
    get_module_levels_for_development,
    setup_logging,
)

# Wallet management
from agentconnect.utils.wallet_manager import (
    load_wallet_data,
    save_wallet_data,
    set_wallet_data_dir,
    set_default_data_dir,
    wallet_exists,
    delete_wallet_data,
    get_all_wallets,
)

# Callbacks
from agentconnect.utils.callbacks import (
    ToolTracerCallbackHandler,
)

__all__ = [
    # Interaction control
    "InteractionControl",
    "InteractionState",
    "TokenConfig",
    "RateLimitingCallbackHandler",
    # Logging
    "setup_logging",
    "LogLevel",
    "disable_all_logging",
    "get_module_levels_for_development",
    # Wallet management
    "load_wallet_data",
    "save_wallet_data",
    "set_wallet_data_dir",
    "set_default_data_dir",
    "wallet_exists",
    "delete_wallet_data",
    "get_all_wallets",
    # Callbacks
    "ToolTracerCallbackHandler",
]
