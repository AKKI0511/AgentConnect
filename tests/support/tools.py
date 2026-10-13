"""Call Team tool descriptors the way a harness does."""

from __future__ import annotations

import inspect
from typing import Any


async def call_team_tool(tools: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    """Invoke the descriptor named `name` and return its JSON result."""
    tool = next(item for item in tools if item.name == name)
    result = tool.handler(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result
