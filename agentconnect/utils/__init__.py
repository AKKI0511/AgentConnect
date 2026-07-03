"""
Utility functions for the AgentConnect framework.

This module provides various utility functions and classes used throughout the framework,
including interaction control for rate limiting, token usage tracking, and wallet management.

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

# Wallet management
from agentconnect.utils.wallet_manager import (
    load_wallet_data,
    save_wallet_data,
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
    # Wallet management
    "load_wallet_data",
    "save_wallet_data",
    "wallet_exists",
    "delete_wallet_data",
    "get_all_wallets",
    # Callbacks
    "ToolTracerCallbackHandler",
]
