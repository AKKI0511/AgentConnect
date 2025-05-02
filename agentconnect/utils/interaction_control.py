"""
Interaction control for the AgentConnect framework.

This module provides rate limiting and interaction tracking for agents,
including token-based rate limiting, automatic cooldown, and integration
with LangChain and LangGraph.
"""

import logging
import time
from dataclasses import dataclass

# Standard library imports
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Third-party imports
from langchain_core.callbacks.base import BaseCallbackHandler

# Set up logging
logger = logging.getLogger(__name__)


class InteractionState(Enum):
    """
    Enum for interaction states.

    Attributes:
        CONTINUE: Continue the interaction
        STOP: Stop the interaction
        WAIT: Wait before continuing the interaction
    """

    CONTINUE = "continue"
    STOP = "stop"
    WAIT = "wait"


class RateLimitingCallbackHandler(BaseCallbackHandler):
    """
    Callback handler that implements rate limiting for LLM calls.

    This handler tracks token usage and enforces rate limits for LLM calls,
    triggering cooldown periods when limits are reached.

    Attributes:
        max_tokens_per_minute: Maximum tokens allowed per minute
        max_tokens_per_hour: Maximum tokens allowed per hour
        current_minute_tokens: Current token count for the minute
        current_hour_tokens: Current token count for the hour
        last_minute_reset: Timestamp of the last minute reset
        last_hour_reset: Timestamp of the last hour reset
        in_cooldown: Whether the handler is in cooldown
        cooldown_until: Timestamp when cooldown ends
        cooldown_callback: Optional callback function to call when cooldown is triggered
    """

    def __init__(
        self,
        max_tokens_per_minute: int = 5500,
        max_tokens_per_hour: int = 100000,
        cooldown_callback: Optional[Callable[[int], None]] = None,
    ):
        """
        Initialize the rate limiting callback handler.

        Args:
            max_tokens_per_minute: Maximum tokens allowed per minute
            max_tokens_per_hour: Maximum tokens allowed per hour
            cooldown_callback: Optional callback function to call when cooldown is triggered
        """
        self.max_tokens_per_minute = max_tokens_per_minute
        self.max_tokens_per_hour = max_tokens_per_hour
        self.current_minute_tokens = 0
        self.current_hour_tokens = 0
        self.last_minute_reset = time.time()
        self.last_hour_reset = time.time()
        self.in_cooldown = False
        self.cooldown_until = 0
        self.cooldown_callback = cooldown_callback
        logger.debug("RateLimitingCallbackHandler initialized")

        # Ensure this callback doesn't interfere with LangSmith tracing
        self.ignore_llm_start = False
        self.ignore_llm_end = False
        self.ignore_chain_start = True  # Ignore chain events to avoid duplicate traces
        self.ignore_chain_end = True  # Ignore chain events to avoid duplicate traces

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """
        Handle LLM start event.

        Args:
            serialized: Serialized LLM data
            prompts: List of prompts
            **kwargs: Additional arguments
        """
        # Check if we're in cooldown
        current_time = time.time()
        if self.in_cooldown and current_time < self.cooldown_until:
            remaining = int(self.cooldown_until - current_time)
            logger.warning(
                f"Rate limit cooldown in effect. {remaining} seconds remaining."
            )
            # We don't raise an exception here because we want to allow the LLM call to proceed
            # The agent should check cooldown state before making calls

    def on_llm_end(self, response, **kwargs: Any) -> None:
        """
        Handle LLM end event.

        Args:
            response: LLM response
            **kwargs: Additional arguments
        """
        # Extract token usage from the response
        token_usage = None

        # Try to get token usage from different response formats
        if hasattr(response, "llm_output") and response.llm_output:
            if (
                isinstance(response.llm_output, dict)
                and "token_usage" in response.llm_output
            ):
                token_usage = response.llm_output["token_usage"]

        # For newer LangChain versions
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            token_usage = response.usage_metadata

        if token_usage:
            # Get total tokens (input + output)
            total_tokens = token_usage.get("total_tokens", 0)
            if total_tokens > 0:
                logger.debug(f"LLM used {total_tokens} tokens")
                self._add_tokens(total_tokens)
        else:
            logger.debug("Could not extract token usage from LLM response")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """
        Handle chain end event.

        Args:
            outputs: Chain outputs
            **kwargs: Additional arguments
        """
        # We don't need to do anything here, but we need to implement this method
        # to avoid warnings from LangChain
        pass

    def _add_tokens(self, token_count: int) -> None:
        """
        Add tokens to the current count and check for rate limits.

        Args:
            token_count: Number of tokens to add
        """
        current_time = time.time()

        # Reset minute counters if needed
        if current_time - self.last_minute_reset >= 60:
            logger.info("Resetting minute token count")
            self.current_minute_tokens = 0
            self.last_minute_reset = current_time

        # Reset hour counters if needed
        if current_time - self.last_hour_reset >= 3600:
            logger.info("Resetting hour token count")
            self.current_hour_tokens = 0
            self.last_hour_reset = current_time

        # Add tokens to counters
        self.current_minute_tokens += token_count
        self.current_hour_tokens += token_count

        logger.debug(
            f"Current minute tokens: {self.current_minute_tokens}/{self.max_tokens_per_minute}, "
            f"Current hour tokens: {self.current_hour_tokens}/{self.max_tokens_per_hour}"
        )

        # Check if we need to enter cooldown
        cooldown_duration = None

        if self.current_minute_tokens >= self.max_tokens_per_minute:
            cooldown_duration = max(60 - (current_time - self.last_minute_reset), 0)
            logger.warning(
                f"Minute token limit reached. Cooldown for {cooldown_duration} seconds"
            )

        elif self.current_hour_tokens >= self.max_tokens_per_hour:
            cooldown_duration = max(3600 - (current_time - self.last_hour_reset), 0)
            logger.warning(
                f"Hour token limit reached. Cooldown for {cooldown_duration} seconds"
            )

        if cooldown_duration:
            self.in_cooldown = True
            self.cooldown_until = current_time + cooldown_duration

            # Call the cooldown callback if provided
            if self.cooldown_callback:
                self.cooldown_callback(int(cooldown_duration))
                logger.debug(
                    f"Cooldown callback executed with duration: {cooldown_duration}"
                )


@dataclass
class TokenConfig:
    """
    Configuration for token-based rate limiting.

    Attributes:
        max_tokens_per_minute: Maximum tokens allowed per minute
        max_tokens_per_hour: Maximum tokens allowed per hour
        current_minute_tokens: Current token count for the minute
        current_hour_tokens: Current token count for the hour
        last_minute_reset: Timestamp of the last minute reset
        last_hour_reset: Timestamp of the last hour reset
    """

    max_tokens_per_minute: int
    max_tokens_per_hour: int
    current_minute_tokens: int = 0
    current_hour_tokens: int = 0
    last_minute_reset: float = time.time()
    last_hour_reset: float = time.time()

    def add_tokens(self, token_count: int) -> None:
        """
        Add tokens to the current count.

        Args:
            token_count: Number of tokens to add
        """
        logger.debug(f"Adding {token_count} tokens.")
        current_time = time.time()

        # Reset minute counters if needed
        if current_time - self.last_minute_reset >= 60:
            logger.info("Resetting minute token count.")
            self.current_minute_tokens = 0
            self.last_minute_reset = current_time

        # Reset hour counters if needed
        if current_time - self.last_hour_reset >= 3600:
            logger.info("Resetting hour token count.")
            self.current_hour_tokens = 0
            self.last_hour_reset = current_time

        self.current_minute_tokens += token_count
        self.current_hour_tokens += token_count
        logger.debug(
            f"Current minute tokens: {self.current_minute_tokens}, Current hour tokens: {self.current_hour_tokens}"
        )

    def get_cooldown_duration(self) -> Optional[int]:
        """
        Get the cooldown duration in seconds if rate limits are exceeded.

        Returns:
            Cooldown duration in seconds, or None if no cooldown is needed
        """
        current_time = time.time()

        if self.current_minute_tokens >= self.max_tokens_per_minute:
            cooldown = max(60 - (current_time - self.last_minute_reset), 0)
            logger.warning(
                f"Minute limit reached. Cooldown duration: {cooldown} seconds."
            )
            return int(cooldown)

        if self.current_hour_tokens >= self.max_tokens_per_hour:
            cooldown = max(3600 - (current_time - self.last_hour_reset), 0)
            logger.warning(
                f"Hour limit reached. Cooldown duration: {cooldown} seconds."
            )
            return int(cooldown)

        return None


@dataclass
class InteractionControl:
    """
    High-level control for agent interactions.

    This class provides rate limiting, turn tracking, and conversation statistics
    for agent interactions.

    Attributes:
        agent_id: The ID of the agent this control belongs to.
        token_config: Configuration for token-based rate limiting
        max_turns: Maximum number of turns in a conversation
        current_turn: Current turn number
        last_interaction_time: Timestamp of the last interaction
        _cooldown_callback: Optional callback function to call when cooldown is triggered
        _conversation_stats: Dictionary of conversation statistics
    """

    agent_id: str
    token_config: TokenConfig
    max_turns: int = 20
    current_turn: int = 0
    last_interaction_time: float = time.time()
    _cooldown_callback: Optional[Callable[[int], None]] = None
    _conversation_stats: Dict[str, Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize conversation stats dictionary."""
        self._conversation_stats = {}
        logger.debug(
            f"InteractionControl initialized for agent {self.agent_id} with max_turns={self.max_turns}"
        )

    async def process_interaction(
        self, token_count: int, conversation_id: Optional[str] = None
    ) -> InteractionState:
        """
        Process an interaction and return the state.

        Args:
            token_count: Number of tokens used in the interaction
            conversation_id: Optional conversation ID for tracking stats

        Returns:
            InteractionState indicating whether to continue, stop, or wait
        """
        logger.debug(f"Processing interaction with {token_count} tokens.")

        # Track conversation stats if ID provided
        if conversation_id:
            if conversation_id not in self._conversation_stats:
                self._conversation_stats[conversation_id] = {
                    "total_tokens": 0,
                    "turn_count": 0,
                    "start_time": time.time(),
                }

            self._conversation_stats[conversation_id]["total_tokens"] += token_count
            self._conversation_stats[conversation_id]["turn_count"] += 1
            self._conversation_stats[conversation_id]["last_time"] = time.time()

            logger.debug(
                f"Conversation {conversation_id} stats: {self._conversation_stats[conversation_id]}"
            )

        # Check if max turns reached before incrementing
        if self.current_turn >= self.max_turns:
            logger.info(
                f"Maximum interaction turns reached ({self.max_turns}). Stopping interaction."
            )
            return InteractionState.STOP

        # No need to add tokens/turns for no response
        if token_count == 0:
            logger.debug("No tokens used, continuing without incrementing counters.")
            return InteractionState.CONTINUE

        # Add tokens and increment turn counter
        self.token_config.add_tokens(token_count)
        self.current_turn += 1
        logger.debug(f"Current turn: {self.current_turn}/{self.max_turns}")

        # Get cooldown duration if needed
        cooldown_duration = self.token_config.get_cooldown_duration()
        if cooldown_duration:
            logger.info(
                f"Interaction is in cooldown state for {cooldown_duration} seconds."
            )

            # Call the cooldown callback if provided
            if self._cooldown_callback:
                self._cooldown_callback(cooldown_duration)
                logger.debug(
                    f"Cooldown callback executed with duration: {cooldown_duration}"
                )

            return InteractionState.WAIT

        logger.info(f"Interaction continues. Turn {self.current_turn}/{self.max_turns}")
        return InteractionState.CONTINUE

    def set_cooldown_callback(self, callback: Callable[[int], None]) -> None:
        """
        Set a callback function to be called when cooldown is triggered.

        Args:
            callback: Function that takes cooldown duration in seconds as argument
        """
        self._cooldown_callback = callback
        logger.debug("Cooldown callback set")

    def reset_turn_counter(self) -> None:
        """Reset the turn counter to zero."""
        self.current_turn = 0
        logger.info("Turn counter reset to 0")

    def get_conversation_stats(
        self, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get statistics for a specific conversation or all conversations.

        Args:
            conversation_id: Optional ID of the conversation to get stats for

        Returns:
            Dictionary of conversation statistics
        """
        if conversation_id:
            return self._conversation_stats.get(conversation_id, {})
        return self._conversation_stats

    def get_callback_handlers(self) -> List[BaseCallbackHandler]:
        """
        Create a list of callback handlers managed by InteractionControl (primarily rate limiting).

        Returns:
            List containing configured BaseCallbackHandler instances.
        """
        callbacks: List[BaseCallbackHandler] = []

        # 1. Add rate limiting callback
        rate_limiter = RateLimitingCallbackHandler(
            max_tokens_per_minute=self.token_config.max_tokens_per_minute,
            max_tokens_per_hour=self.token_config.max_tokens_per_hour,
            cooldown_callback=self._cooldown_callback,
        )
        callbacks.append(rate_limiter)
        logger.debug("Added rate limiting callback to callback manager")

        # We're not adding a LangChain tracer here to avoid duplicate traces in LangSmith
        # LangSmith will automatically trace the workflow if LANGCHAIN_TRACING is enabled

        return callbacks
