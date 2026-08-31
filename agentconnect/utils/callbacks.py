"""Lightweight activity logger for prebuilt helpers.

This is not a model-framework callback. It prints tool names when asked.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ToolTracerCallbackHandler:
    """Log tool names for one Agent. Optional console print.

    tracer = ToolTracerCallbackHandler("assistant")
    tracer.on_tool("find", {"matches": []})
    """

    def __init__(
        self,
        agent_id: str,
        print_tool_activity: bool = True,
        print_reasoning_steps: bool = False,
    ) -> None:
        """Bind ``agent_id``. ``print_reasoning_steps`` is accepted and ignored."""
        del print_reasoning_steps
        self.agent_id = agent_id
        self.print_tool_activity = print_tool_activity

    def on_tool(self, name: str, result: Any = None) -> None:
        """Record that ``name`` ran."""
        logger.info("tool %s agent_id=%s", name, self.agent_id)
        if self.print_tool_activity:
            print(f"[{self.agent_id}] tool {name}")
