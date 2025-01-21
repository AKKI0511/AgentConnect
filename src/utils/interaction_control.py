from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time
import logging

# Import the logging configuration
from src.utils.logging_config import setup_logging, LogLevel

# Set up logging
setup_logging(level=LogLevel.DEBUG)

# Create a logger for this module
logger = logging.getLogger(__name__)


class InteractionState(Enum):
    CONTINUE = "continue"
    STOP = "stop"
    WAIT = "wait"


@dataclass
class TokenConfig:
    max_tokens_per_minute: int
    max_tokens_per_hour: int
    current_minute_tokens: int = 0
    current_hour_tokens: int = 0
    last_minute_reset: float = time.time()
    last_hour_reset: float = time.time()

    def add_tokens(self, token_count: int) -> None:
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
        """Returns the cooldown duration in seconds"""
        current_time = time.time()

        if self.current_minute_tokens >= self.max_tokens_per_minute:
            cooldown = max(60 - (current_time - self.last_minute_reset), 0)
            logger.warning(
                f"Minute limit reached. Cooldown duration: {cooldown} seconds."
            )
            return cooldown

        if self.current_hour_tokens >= self.max_tokens_per_hour:
            cooldown = max(3600 - (current_time - self.last_hour_reset), 0)
            logger.warning(
                f"Hour limit reached. Cooldown duration: {cooldown} seconds."
            )
            return cooldown

        return None


@dataclass
class InteractionControl:
    token_config: TokenConfig
    max_turns: int = 1
    current_turn: int = 0
    last_interaction_time: float = time.time()

    async def process_interaction(self, token_count: int) -> InteractionState:
        """Process an interaction and return the state"""
        logger.debug(f"Processing interaction with {token_count} tokens.")

        # Check if max turns reached before incrementing
        if self.current_turn >= self.max_turns:
            logger.info("Maximum interaction turns reached. Stopping interaction.")
            return InteractionState.STOP

        # No need to add tokens/turns for no response
        if token_count == 0:
            return InteractionState.CONTINUE

        # Add tokens and increment turn counter
        self.token_config.add_tokens(token_count)
        self.current_turn += 1
        logger.debug(f"Current turn: {self.current_turn}")

        # Get cooldown duration if needed
        cooldown_duration = self.token_config.get_cooldown_duration()
        if cooldown_duration:
            logger.info("Interaction is in cooldown state.")
            return InteractionState.WAIT

        logger.info("Interaction continues.")
        return InteractionState.CONTINUE
