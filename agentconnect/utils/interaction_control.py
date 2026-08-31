"""Turn and token tracking for prebuilt helpers.

This module no longer depends on LangChain. ``InteractionControl`` counts
tokens and turns. Cooldown still goes through ``BaseAgent.set_cooldown``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class InteractionState(Enum):
    """What the helper should do after a turn."""

    CONTINUE = "continue"
    STOP = "stop"
    WAIT = "wait"


@dataclass
class TokenConfig:
    """Per-minute and per-hour token caps."""

    max_tokens_per_minute: int = 70000
    max_tokens_per_hour: int = 700000


class RateLimitingCallbackHandler:
    """Records token usage. Not a model-framework callback."""

    def __init__(
        self,
        max_tokens_per_minute: int,
        max_tokens_per_hour: int,
        on_limit: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Bind caps and an optional cooldown callback."""
        self.max_tokens_per_minute = max_tokens_per_minute
        self.max_tokens_per_hour = max_tokens_per_hour
        self.on_limit = on_limit
        self.current_minute_tokens = 0
        self.current_hour_tokens = 0
        self.minute_start = time.time()
        self.hour_start = time.time()

    def add_tokens(self, token_count: int) -> InteractionState:
        """Add ``token_count`` and return STOP when a cap is hit."""
        now = time.time()
        if now - self.minute_start >= 60:
            self.current_minute_tokens = 0
            self.minute_start = now
        if now - self.hour_start >= 3600:
            self.current_hour_tokens = 0
            self.hour_start = now
        self.current_minute_tokens += token_count
        self.current_hour_tokens += token_count
        if (
            self.current_minute_tokens >= self.max_tokens_per_minute
            or self.current_hour_tokens >= self.max_tokens_per_hour
        ):
            if self.on_limit is not None:
                self.on_limit(60)
            return InteractionState.WAIT
        return InteractionState.CONTINUE


class InteractionControl:
    """Turn counter plus token caps for one Agent."""

    def __init__(
        self,
        agent_id: str,
        token_config: Optional[TokenConfig] = None,
        max_turns: int = 20,
    ) -> None:
        """Bind ``agent_id`` and optional caps."""
        self.agent_id = agent_id
        self.token_config = token_config or TokenConfig()
        self.max_turns = max_turns
        self.turn_count = 0
        self._cooldown: Optional[Callable[[int], None]] = None
        self._limiter = RateLimitingCallbackHandler(
            self.token_config.max_tokens_per_minute,
            self.token_config.max_tokens_per_hour,
        )
        self._stats: Dict[str, Dict[str, int]] = {}

    def set_cooldown_callback(self, callback: Callable[[int], None]) -> None:
        """Called with a duration in seconds when a token cap is hit."""
        self._cooldown = callback
        self._limiter.on_limit = callback

    def get_callback_handlers(self) -> List[Any]:
        """Return the token limiter. Kept so older call sites still compile."""
        return [self._limiter]

    def reset_turn_counter(self) -> None:
        """Set the turn count back to zero."""
        self.turn_count = 0

    def get_conversation_stats(self) -> Dict[str, Dict[str, int]]:
        """Return per-conversation token and turn counts."""
        return dict(self._stats)

    async def process_interaction(
        self, token_count: int = 0, conversation_id: str = "default"
    ) -> InteractionState:
        """Record one turn. STOP when ``max_turns`` is reached."""
        self.turn_count += 1
        stats = self._stats.setdefault(
            conversation_id, {"total_tokens": 0, "turn_count": 0}
        )
        stats["total_tokens"] += int(token_count)
        stats["turn_count"] += 1
        state = self._limiter.add_tokens(int(token_count))
        if self.turn_count >= self.max_turns:
            return InteractionState.STOP
        return state
