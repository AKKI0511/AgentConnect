"""Team MCP server: discovery, send, collect, roster, extra tools.

One MCP server per Team, built on the 2026-07-28 stateless MCP spec
(`https://py.sdk.modelcontextprotocol.io/`). Members point a model at it.
So does any MCP client, including Cursor, by adding the Team MCP URL.

    from agentconnect import Team
    from agentconnect.mcp import create_team_mcp

    team = await Team("content-squad").start()
    url = await team.serve()
    print(team.mcp_url)  # http://127.0.0.1:<port>/mcp

The MCP SDK's OAuth resource-server helpers need issuer metadata and wrap
every HTTP method, including initialize. That does not match Session Bearer
tokens or loopback operator. This server uses SDK ``ServerMiddleware`` for
authentication and raw ``tools/call`` argument checks.

Do not add ``from __future__ import annotations`` here. MCPServer injects
``Context`` from the live type annotation.
"""

import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from typing import Any, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS, ToolAnnotations

from agentconnect.core.base import dump_public, parse_schema
from agentconnect.core.directory import FindRequest
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
)
from agentconnect.mcp.actions import (
    TeamRuntime,
    ask_action,
    find_action,
    get_history_action,
    get_result_action,
    tell_action,
)
from agentconnect.mcp.tool_schema import (
    advertise_tool_schema,
    close_fixed_extra_tool_schemas,
    tool_argument_keys,
)
from agentconnect.team.constants import RESERVED_MCP_TOOL_NAMES
from agentconnect.team.errors import TeamError
from agentconnect.team.session_auth import session_token_for_request

_INSTRUCTIONS = (
    "You are talking to an AgentConnect Team. Use find to discover teammates "
    "by describing the work. Use ask to send reply-expected work. Use tell "
    "for events. Use get_result to collect a Ticket. Use get_history to page "
    "a conversation. Addresses look like writer or writer@team-name. Keep "
    "ticket.id and thread_id from results. ask wait may return an open "
    "Ticket; call get_result for the rest. Do not invent thread ids. Pass "
    "idempotency_key when you mean to retry the same ask."
)

_PROTECTED_METHODS = frozenset({"tools/call", "resources/read"})
_TOOL_MODELS = {
    "find": FindRequest,
    "ask": AskToolRequest,
    "tell": TellToolRequest,
    "get_result": GetResultRequest,
    "get_history": GetHistoryRequest,
}
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
    """SDK ServerMiddleware: Session auth, then raw tools/call argument checks."""

    def __init__(
        self,
        runtime: TeamRuntime,
        *,
        in_process: bool,
        extra_tools: Mapping[str, Callable[..., Any]],
    ) -> None:
        """Bind the Runtime, hosting mode, and extra tool signatures."""
        self._runtime = runtime
        self._in_process = in_process
        self._extra_tools = dict(extra_tools)

    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        """Authenticate the caller, then reject invalid raw tool arguments."""
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
            if method == "tools/call":
                self._reject_raw_arguments(getattr(ctx, "params", None))
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

    def _reject_raw_arguments(self, params: Any) -> None:
        """Validate original tool arguments before SDK coercion."""
        if hasattr(params, "model_dump") and not isinstance(params, Mapping):
            params = params.model_dump()
        if not isinstance(params, Mapping):
            raise MCPError(INVALID_PARAMS, "tool params must be an object")
        name = params.get("name")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, Mapping):
            raise MCPError(INVALID_PARAMS, "arguments must be an object")
        raw = dict(arguments)
        model = _TOOL_MODELS.get(str(name)) if name is not None else None
        if model is not None:
            try:
                parse_schema(model, raw)
            except ValueError as exc:
                raise MCPError(INVALID_PARAMS, str(exc)) from exc
            return
        extra = self._extra_tools.get(str(name)) if name is not None else None
        if extra is None:
            return
        allowed = tool_argument_keys(extra)
        if allowed is None:
            return
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise MCPError(INVALID_PARAMS, f"unexpected argument {unknown[0]!r}")


def _bound_session() -> str:
    """Return the Session stored by :class:`_TeamBoundary`."""
    token = _resolved_session.get()
    if not token:
        raise MCPError(INVALID_PARAMS, "Session is missing or invalid")
    return token


def create_team_mcp(
    runtime: TeamRuntime,
    extra_tools: Sequence[Callable[..., Any]] | None = None,
    *,
    in_process: bool = True,
) -> MCPServer:
    """Return the MCP server for ``runtime``.

    Tools are ``find``, ``ask``, ``tell``, ``get_result``, and ``get_history``.
    The roster is the resource ``agentconnect://team/roster``. Extra callables
    are registered by function name and must not reuse a reserved name.

    ``in_process=True`` (the default) is the explicit in-process trust path
    used by ``Client(mcp)``. HTTP serving passes ``in_process=False`` so a
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
    extra_by_name: dict[str, Callable[..., Any]] = {}
    for fn in extras:
        name = getattr(fn, "__name__", "")
        if name in RESERVED_MCP_TOOL_NAMES:
            raise ValueError(f"tool name {name!r} is reserved")
        extra_by_name[name] = fn

    mcp = MCPServer(
        name=f"agentconnect-{runtime.name}",
        version="1.0.0-draft",
        instructions=_INSTRUCTIONS,
        middleware=[
            _TeamBoundary(runtime, in_process=in_process, extra_tools=extra_by_name)
        ],
    )

    async def find(
        ctx: Context,
        query: str,
        limit: Optional[int] = None,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Find teammates by describing the work you need.

        query: Natural-language need, for example "someone who can review a contract".
        limit: Maximum matches from 1 to 100. Omit to receive every other member.
        detail: "summary" (default) or "full".
        """
        del ctx
        token = _bound_session()
        try:
            return await find_action(runtime, token, query, limit=limit, detail=detail)
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def ask(
        ctx: Context,
        recipient: str,
        content: Any,
        deadline_seconds: Optional[int] = None,
        collect: str = "wait",
        thread_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send reply-expected work and return the current Ticket.

        recipient: Local Address such as "writer".
        content: The work, text or JSON.
        deadline_seconds: Optional work cutoff from 1 to 86400 seconds. Omit to inherit a request parent or the Runtime work lifetime.
        collect: "wait" (default) returns the current Ticket after the Runtime hold, which may still be open. "ticket" returns immediately.
        thread_id: Continue this conversation. Omit to start a new one.
        idempotency_key: Stable key so a retry does not create a second request.
        """
        token = _bound_session()
        address = await runtime.caller_address(token)
        del ctx
        try:
            return await ask_action(
                runtime,
                token,
                address,
                recipient,
                content,
                deadline_seconds=deadline_seconds,
                collect=collect,
                thread_id=thread_id,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def tell(
        ctx: Context,
        recipient: str,
        content: Any,
        thread_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an event. No Ticket is created.

        recipient: Local Address such as "writer".
        content: The event, text or JSON.
        thread_id: Continue this conversation.
        idempotency_key: Stable key so a retry does not create a second event.
        """
        token = _bound_session()
        address = await runtime.caller_address(token)
        del ctx
        try:
            return await tell_action(
                runtime,
                token,
                address,
                recipient,
                content,
                thread_id=thread_id,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def get_result(ctx: Context, ticket_id: str) -> dict[str, Any]:
        """Return the current Ticket for work this Membership sent.

        ticket_id: Ticket id from ask. Equal to the request Message id.
        """
        del ctx
        token = _bound_session()
        try:
            return await get_result_action(runtime, token, ticket_id)
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def get_history(
        ctx: Context,
        thread_id: str,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history.

        thread_id: Conversation id from a Ticket or Message.
        before: Oldest Message id already seen. Omit for the newest page.
        limit: Page size from 1 to 200. Defaults to 50.
        """
        del ctx
        token = _bound_session()
        try:
            return await get_history_action(
                runtime, token, thread_id, before=before, limit=limit
            )
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def roster() -> str:
        """Return the Team roster as JSON text."""
        body = dump_public(await runtime.roster())
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    mcp.add_tool(
        find,
        name="find",
        title="Find teammates",
        description=(
            "Find teammates by describing the work you need. Returns ranked "
            "matches. Omit limit to receive every other member, at most 100."
        ),
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    mcp.add_tool(
        ask,
        name="ask",
        title="Ask a teammate",
        description=(
            "Send reply-expected work. Returns a Ticket. Keep ticket.id and "
            "pass it to get_result if the Ticket is still open."
        ),
        annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
        structured_output=True,
    )
    mcp.add_tool(
        tell,
        name="tell",
        title="Tell a teammate",
        description="Send an event. No reply is expected and no Ticket is created.",
        annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
        structured_output=True,
    )
    mcp.add_tool(
        get_result,
        name="get_result",
        title="Collect a result",
        description="Return the current Ticket. Repeatable. Does not consume the result.",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    mcp.add_tool(
        get_history,
        name="get_history",
        title="Reload a conversation",
        description="Return one page of retained Thread history, newest page first.",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    mcp.resource(
        "agentconnect://team/roster",
        name="roster",
        title="Team roster",
        description="Agent Memberships on this Team. Principals such as operator are omitted.",
        mime_type="application/json",
    )(roster)

    for fn in extras:
        name = getattr(fn, "__name__", "tool")
        mcp.add_tool(
            fn,
            name=name,
            description=inspect.getdoc(fn) or name,
        )
    for name, model in _TOOL_MODELS.items():
        advertise_tool_schema(mcp, name, model)
    close_fixed_extra_tool_schemas(mcp, extra_by_name)
    return mcp


def _tool_error(exc: TeamError) -> ToolError:
    """Wrap a Runtime error as an MCP tool error payload."""
    payload = {"error": exc.to_error_object()}
    return ToolError(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
