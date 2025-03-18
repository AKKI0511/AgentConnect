"""
Utility functions for the AgentConnect framework.

This module provides various utility functions and classes used throughout the framework,
including interaction control for rate limiting, token usage tracking, and logging configuration.

Key components:
- InteractionControl: Controls agent interactions with rate limiting and turn tracking
- InteractionState: Enum for interaction states (CONTINUE, STOP, WAIT)
- TokenConfig: Configuration for token-based rate limiting
- Logging utilities: Configurable logging setup with colored output
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
]
