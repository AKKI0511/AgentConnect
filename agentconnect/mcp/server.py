"""Team MCP server: discovery, send, collect, roster, extra tools.

One MCP server per Team, built on the SDK low-level ``Server`` so advertised
schemas are the public argument and result types. Members point a model at
it. So does any MCP client, including Cursor, by adding the Team MCP URL.

    from agentconnect import Team
    from agentconnect.mcp import create_team_mcp

    team = await Team("content-squad").start()
    url = await team.serve()
    print(team.mcp_url)  # http://127.0.0.1:<port>/mcp

The SDK's OAuth resource-server helpers need issuer metadata and wrap every
HTTP method, including initialize. That does not match Session Bearer tokens
or loopback operator. This server uses SDK ``Server.middleware`` for
authentication. ``Server`` does not apply ``input_schema`` to calls, so
``tools/call`` validates public argument types before dispatch.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from typing import Any

from mcp.server import CacheHint, Server
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver.context import Context as SdkContext
from mcp.server.mcpserver.exceptions import ToolError as SdkToolError
from mcp.server.mcpserver.exceptions import UnexpectedToolError
from mcp.server.mcpserver.tools.base import Tool as SdkTool
from mcp.shared.exceptions import MCPError
from mcp_types import (
    INVALID_PARAMS,
    CallToolResult,
    InputRequiredResult,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
    Resource,
    TextContent,
    TextResourceContents,
    Tool,
    ToolAnnotations,
)

from agentconnect.core.base import (
    dump_public,
    parse_schema,
    public_json_schema,
    public_result_schema,
)
from agentconnect.core.error import ErrorObject
from agentconnect.core.operations import ToolErrorResult
from agentconnect.core.team_tools import (
    RESERVED_TEAM_TOOL_NAMES,
    TEAM_MCP_INSTRUCTIONS,
    TEAM_TOOL_BY_NAME,
    TEAM_TOOL_SPECS,
    TeamToolSpec,
)
from agentconnect.mcp.actions import (
    TeamRuntime,
    ask_action,
    find_action,
    get_history_action,
    get_profiles_action,
    get_result_action,
    tell_action,
)
from agentconnect.team.errors import TeamError
from agentconnect.team.session_auth import session_token_for_request

logger = logging.getLogger(__name__)

_INSTRUCTIONS = TEAM_MCP_INSTRUCTIONS
_ROSTER_URI = "agentconnect://team/roster"
_HISTORY_DEFAULT_LIMIT = 50

# MCP 2026-07-28: omitted ttlMs lets a client apply its own catalog heuristic.
# ttl_ms=0 is immediately stale. The catalog is built once; there is no
# list-change publisher, so listChanged follows that static surface.
_CATALOG_CACHE_HINTS = {
    "tools/list": CacheHint(ttl_ms=0),
    "server/discover": CacheHint(ttl_ms=0),
}

_PROTECTED_METHODS = frozenset({"tools/call", "resources/read"})
_READ_ONLY_TOOLS = frozenset({"find", "get_result", "get_history", "get_profiles"})
_resolved_session: ContextVar[str | None] = ContextVar(
    "agentconnect_mcp_session", default=None
)


def _http_peer(ctx: Any) -> tuple[Mapping[str, str] | None, str | None]:
    """Return headers and peer host from the SDK request context, if any."""
    request = getattr(ctx, "request", None)
    headers = getattr(request, "headers", None) if request is not None else None
    client = getattr(request, "client", None) if request is not None else None
    peer_host = client.host if client is not None else None
    return headers, peer_host


class _TeamBoundary:
    """SDK ServerMiddleware: Session auth for tool calls and resource reads."""

    def __init__(self, runtime: TeamRuntime, *, in_process: bool) -> None:
        """Bind the Runtime and hosting mode."""
        self._runtime = runtime
        self._in_process = in_process

    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        """Authenticate protected methods, then continue the SDK chain."""
        method = getattr(ctx, "method", None)
        if method not in _PROTECTED_METHODS:
            return await call_next(ctx)
        headers, peer_host = _http_peer(ctx)
        token_holder = None
        try:
            token = await session_token_for_request(
                self._runtime,
                headers,
                peer_host=peer_host,
                in_process=self._in_process,
            )
            token_holder = _resolved_session.set(token)
            request = getattr(ctx, "request", None)
            state = getattr(request, "state", None) if request is not None else None
            if state is not None:
                state.session_token = token
            return await call_next(ctx)
        except TeamError as exc:
            if exc.code == "unauthorized":
                raise MCPError(INVALID_PARAMS, exc.message) from exc
            raise
        finally:
            if token_holder is not None:
                _resolved_session.reset(token_holder)


def _bound_session() -> str:
    """Return the Session stored by :class:`_TeamBoundary`."""
    token = _resolved_session.get()
    if not token:
        raise MCPError(INVALID_PARAMS, "Session is missing or invalid")
    return token


def _listed_team_tool(spec: TeamToolSpec) -> Tool:
    """Return the advertised Tool for one reserved Team operation."""
    return Tool(
        name=spec.name,
        title=spec.title,
        description=spec.description,
        input_schema=public_json_schema(spec.input_model),
        output_schema=public_result_schema(spec.output_model),
        annotations=ToolAnnotations(
            read_only_hint=spec.name in _READ_ONLY_TOOLS,
            open_world_hint=False,
        ),
    )


def _listed_extra_tool(tool: SdkTool) -> Tool:
    """Return the advertised Tool copied from an SDK callable tool."""
    return Tool(
        name=tool.name,
        title=tool.title,
        description=tool.description or tool.name,
        input_schema=tool.parameters,
        output_schema=tool.output_schema,
        annotations=tool.annotations,
        icons=tool.icons,
        meta=tool.meta,
    )


def _sdk_extra_tools(fns: Sequence[Callable[..., Any]]) -> dict[str, SdkTool]:
    """Build SDK tools for extra callables, rejecting reserved and duplicate names."""
    extras: dict[str, SdkTool] = {}
    for fn in fns:
        tool = SdkTool.from_function(fn)
        if tool.name in RESERVED_TEAM_TOOL_NAMES:
            raise ValueError(f"tool name {tool.name!r} is reserved")
        if tool.name in extras:
            raise ValueError(f"tool name {tool.name!r} is already registered")
        extras[tool.name] = tool
    return extras


def _success_result(payload: Any) -> CallToolResult:
    """Return structured content plus JSON text for the model."""
    body = dump_public(payload)
    text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    if not isinstance(body, dict):
        return CallToolResult(content=[TextContent(type="text", text=text)])
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=body,
    )


def _tool_error(exc: TeamError) -> CallToolResult:
    """Wrap a Runtime error as a structured MCP tool error.

    Returning ``CallToolResult`` with ``is_error`` is the SDK-supported
    path and skips success output-schema validation.
    """
    payload = dump_public(
        ToolErrorResult(error=ErrorObject.model_validate(exc.to_error_object()))
    )
    return CallToolResult(
        content=[TextContent(type="text", text=f"{exc.code}: {exc.message}")],
        structured_content=payload,
        is_error=True,
    )


async def _run_team_tool(
    runtime: TeamRuntime, spec: TeamToolSpec, raw: Mapping[str, Any]
) -> CallToolResult:
    """Validate ``raw`` as ``spec`` and run the matching Runtime action."""
    try:
        parsed = parse_schema(spec.input_model, dict(raw))
    except ValueError as exc:
        raise MCPError(INVALID_PARAMS, str(exc)) from exc
    token = _bound_session()
    try:
        if spec.name == "find":
            payload = await find_action(
                runtime, token, parsed.query, limit=parsed.limit
            )
        elif spec.name == "get_profiles":
            payload = await get_profiles_action(runtime, token, list(parsed.addresses))
        elif spec.name == "ask":
            address = await runtime.caller_address(token)
            payload = await ask_action(
                runtime,
                token,
                address,
                parsed.recipient,
                parsed.content,
                deadline_seconds=parsed.deadline_seconds,
                collect=parsed.collect,
                thread_id=parsed.thread_id,
                idempotency_key=parsed.idempotency_key,
            )
        elif spec.name == "tell":
            address = await runtime.caller_address(token)
            payload = await tell_action(
                runtime,
                token,
                address,
                parsed.recipient,
                parsed.content,
                thread_id=parsed.thread_id,
                idempotency_key=parsed.idempotency_key,
            )
        elif spec.name == "get_result":
            payload = await get_result_action(runtime, token, parsed.ticket_id)
        elif spec.name == "get_history":
            limit = _HISTORY_DEFAULT_LIMIT if parsed.limit is None else parsed.limit
            payload = await get_history_action(
                runtime,
                token,
                parsed.thread_id,
                before=parsed.before,
                limit=limit,
            )
        else:
            raise MCPError(INVALID_PARAMS, f"unknown tool {spec.name!r}")
    except ValueError as exc:
        raise MCPError(INVALID_PARAMS, str(exc)) from exc
    except TeamError as exc:
        return _tool_error(exc)
    return _success_result(payload)


async def _run_extra_tool(
    tool: SdkTool,
    raw: Mapping[str, Any],
    ctx: ServerRequestContext[Any],
) -> CallToolResult | InputRequiredResult:
    """Run an extra callable through the SDK tool implementation."""
    try:
        return await tool.run(
            dict(raw),
            SdkContext(request_context=ctx),
            convert_result=True,
        )
    except MCPError:
        raise
    except Exception as exc:
        if isinstance(exc, SdkToolError) and not isinstance(exc, UnexpectedToolError):
            logger.info("Tool %r failed: %r", tool.name, str(exc))
        else:
            logger.exception("Tool %r raised an unexpected exception", tool.name)
        return CallToolResult(
            content=[TextContent(type="text", text=str(exc))],
            is_error=True,
        )


def create_team_mcp(
    runtime: TeamRuntime,
    extra_tools: Sequence[Callable[..., Any]] | None = None,
    *,
    in_process: bool = True,
) -> Server:
    """Return the MCP server for ``runtime``.

    Tools are ``find``, ``ask``, ``tell``, ``get_result``, ``get_history``,
    and ``get_profiles``. The roster is the resource
    ``agentconnect://team/roster``. Extra callables are registered by
    function name and must not reuse a reserved or duplicate name.

    ``in_process=True`` (the default) is the explicit in-process trust path
    used by ``Client(server)``. HTTP serving passes ``in_process=False`` so a
    missing request cannot become operator.

        mcp = create_team_mcp(team)
        async with Client(mcp) as client:
            found = await client.call_tool("find", {"query": "draft a summary"})
    """
    extras = list(
        extra_tools
        if extra_tools is not None
        else list(getattr(runtime, "_extra_tools", []) or [])
    )
    extra_by_name = _sdk_extra_tools(extras)

    listed_tools = [_listed_team_tool(spec) for spec in TEAM_TOOL_SPECS]
    listed_tools.extend(_listed_extra_tool(tool) for tool in extra_by_name.values())
    schemas_by_name = {tool.name: tool.input_schema for tool in listed_tools}
    roster = Resource(
        name="roster",
        title="Team roster",
        uri=_ROSTER_URI,
        description="Teammates on this Team. The operator is omitted.",
        mime_type="application/json",
    )

    async def on_list_tools(
        ctx: ServerRequestContext[Any], params: Any
    ) -> ListToolsResult:
        """Return the reserved Team tools, then extras, in stable order."""
        del ctx, params
        return ListToolsResult(tools=listed_tools)

    async def on_call_tool(
        ctx: ServerRequestContext[Any], params: Any
    ) -> CallToolResult | InputRequiredResult:
        """Dispatch ``tools/call`` after public-schema argument checks."""
        name = str(params.name)
        arguments = params.arguments
        raw = dict(arguments) if isinstance(arguments, Mapping) else {}
        spec = TEAM_TOOL_BY_NAME.get(name)
        if spec is not None:
            return await _run_team_tool(runtime, spec, raw)
        extra = extra_by_name.get(name)
        if extra is None:
            raise MCPError(INVALID_PARAMS, f"unknown tool {name!r}")
        return await _run_extra_tool(extra, raw, ctx)

    async def on_list_resources(
        ctx: ServerRequestContext[Any], params: Any
    ) -> ListResourcesResult:
        """Return the Team roster resource."""
        del ctx, params
        return ListResourcesResult(resources=[roster])

    async def on_read_resource(
        ctx: ServerRequestContext[Any], params: Any
    ) -> ReadResourceResult:
        """Return roster JSON for the reserved roster URI."""
        del ctx
        if str(params.uri) != _ROSTER_URI:
            raise MCPError(INVALID_PARAMS, f"unknown resource {params.uri!r}")
        body = dump_public(await runtime.roster())
        text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        return ReadResourceResult(
            contents=[
                TextResourceContents(
                    uri=_ROSTER_URI,
                    mime_type="application/json",
                    text=text,
                )
            ]
        )

    def get_tool_input_schema(name: str) -> Mapping[str, Any] | None:
        """Return the advertised input schema by tool name."""
        return schemas_by_name.get(name)

    mcp = Server(
        name=f"agentconnect-{runtime.name}",
        version="1.0.0-draft",
        instructions=_INSTRUCTIONS,
        cache_hints=_CATALOG_CACHE_HINTS,
        get_tool_input_schema=get_tool_input_schema,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
        on_list_resources=on_list_resources,
        on_read_resource=on_read_resource,
    )
    mcp.middleware.append(_TeamBoundary(runtime, in_process=in_process))
    return mcp
