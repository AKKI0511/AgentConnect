"""Utility functions used by optional extras.

Wallet files, payment checks, and a small tool-activity logger.
"""

from agentconnect.utils.callbacks import (
    ToolTracerCallbackHandler,
)
from agentconnect.utils.interaction_control import (
    InteractionControl,
    InteractionState,
    RateLimitingCallbackHandler,
    TokenConfig,
)
from agentconnect.utils.wallet_manager import (
    delete_wallet_data,
    get_all_wallets,
    load_wallet_data,
    save_wallet_data,
    wallet_exists,
)

__all__ = [
    "InteractionControl",
    "InteractionState",
    "TokenConfig",
    "RateLimitingCallbackHandler",
    "load_wallet_data",
    "save_wallet_data",
    "wallet_exists",
    "delete_wallet_data",
    "get_all_wallets",
    "ToolTracerCallbackHandler",
]
