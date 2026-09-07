"""Advertise public argument schemas on MCP tools.

``MCPServer.add_tool`` has no input-schema argument. ``Tool.from_function``
always builds ``parameters`` from the handler signature. This adapter
replaces that generated schema after registration so ``tools/list`` matches
the raw ``tools/call`` boundary.

Unmodified pydantic schemas from handler signatures treat omit-only fields
as ``integer | null`` with ``default: null`` and omit bounds. Do not use
them as the advertised contract.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from agentconnect.core.base import SchemaModel, public_json_schema


def tool_argument_keys(fn: Callable[..., Any]) -> frozenset[str] | None:
    """Return advertised argument names for an extra tool, excluding Context.

    ``None`` means the callable accepts arbitrary keywords.
    """
    names: list[str] = []
    for name, param in inspect.signature(fn).parameters.items():
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            return None
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        annotation = param.annotation
        if annotation is Context or getattr(annotation, "__name__", "") == "Context":
            continue
        names.append(name)
    return frozenset(names)


def _tool(mcp: MCPServer, name: str) -> Any:
    """Return the SDK tool registered as ``name``."""
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None:
        raise KeyError(name)
    tool = manager.get_tool(name)
    if tool is None:
        raise KeyError(name)
    return tool


def advertise_tool_schema(
    mcp: MCPServer, name: str, model: type[SchemaModel]
) -> dict[str, Any]:
    """Set ``tools/list`` parameters for ``name`` from ``model``.

    Returns the schema that was assigned.
    """
    tool = _tool(mcp, name)
    schema = public_json_schema(model)
    tool.parameters = schema
    return schema


def close_fixed_extra_tool_schemas(
    mcp: MCPServer, extra_tools: Mapping[str, Callable[..., Any]]
) -> None:
    """Close extras whose signature does not accept ``**kwargs``.

    An extension that takes arbitrary keywords keeps the schema the SDK
    inferred. Do not set ``additionalProperties: false`` on that tool.
    """
    for name, fn in extra_tools.items():
        allowed = tool_argument_keys(fn)
        if allowed is None:
            continue
        try:
            registered = _tool(mcp, name)
        except KeyError:
            continue
        if isinstance(registered.parameters, dict):
            registered.parameters["additionalProperties"] = False
