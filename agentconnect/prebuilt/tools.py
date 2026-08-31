"""Callable tools for the prebuilt model loop.

A :class:`Tool` is a name, a JSON Schema, and a handler. ``AIAgent`` advertises
these to the model and runs the handler when the model calls the name. Team
tools from :meth:`~agentconnect.agent.base.BaseAgent.team_tools` use the same
shape, so a custom tool and ``find`` look the same to the model.

    from agentconnect.prebuilt import AIAgent, Tool

    async def search_docs(query: str) -> str:
        return f"no hits for {query}"

    agent = AIAgent(
        name="researcher",
        model="gpt-4o-mini",
        tools=[
            Tool(
                name="search_docs",
                description="Search internal docs.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search."}
                    },
                    "required": ["query"],
                },
                handler=search_docs,
            )
        ],
    )
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Union

from agentconnect.agent.tools import TeamTool, TeamTools

ToolHandler = Callable[..., Union[Any, Awaitable[Any]]]


@dataclass(frozen=True)
class Tool:
    """One function the model may call.

    ``parameters`` is a JSON Schema object. ``handler`` receives the model's
    arguments as keyword arguments. Sync and async handlers both work.

        async def ping() -> str:
            return "pong"

        Tool(
            name="ping",
            description="Return pong.",
            parameters={"type": "object", "properties": {}},
            handler=ping,
        )
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def openai_schema(self) -> dict[str, Any]:
        """Return the OpenAI/LiteLLM function-tool descriptor for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def tools_from_team(team_tools: TeamTools | Sequence[TeamTool]) -> list[Tool]:
    """Wrap Session-bound Team tools as :class:`Tool` values.

    tools = tools_from_team(agent.team_tools())
    """
    return [
        Tool(
            name=item.name,
            description=item.description,
            parameters=dict(item.parameters),
            handler=item.coroutine,
        )
        for item in team_tools
    ]


async def call_tool(tool: Tool, arguments: Mapping[str, Any] | str) -> str:
    """Run ``tool.handler`` and return a string the model can read."""
    parsed = _parse_arguments(arguments)
    try:
        if _wants_kwargs(tool.handler):
            result = tool.handler(**parsed)
        else:
            result = tool.handler(parsed)
        if inspect.isawaitable(result):
            result = await result
    except TypeError:
        result = tool.handler(parsed)
        if inspect.isawaitable(result):
            result = await result
    return _stringify(result)


def merge_tools(*groups: Sequence[Tool] | None) -> list[Tool]:
    """Concatenate tool groups. A later tool with the same name replaces an earlier one."""
    by_name: dict[str, Tool] = {}
    for group in groups:
        if not group:
            continue
        for tool in group:
            by_name[tool.name] = tool
    return list(by_name.values())


def _parse_arguments(arguments: Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(arguments, Mapping):
        return dict(arguments)
    raw = arguments.strip() if arguments else ""
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


def _wants_kwargs(handler: ToolHandler) -> bool:
    try:
        inspect.signature(handler)
    except (TypeError, ValueError):
        return True
    return True


def _stringify(result: Any) -> str:
    if result is None:
        return "null"
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str)
    except TypeError:
        return str(result)
