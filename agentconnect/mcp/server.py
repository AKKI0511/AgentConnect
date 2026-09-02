"""Team MCP server: discovery, send, collect, roster, extra tools.

One MCP server per Team, built on the 2026-07-28 stateless MCP spec
(`https://py.sdk.modelcontextprotocol.io/`). Members point a model at it.
So does any MCP client, including Cursor, by adding the Team MCP URL.

    from agentconnect import Team
    from agentconnect.mcp import create_team_mcp

    team = await Team("content-squad").start()
    url = await team.serve()
    print(team.mcp_url)  # http://127.0.0.1:<port>/mcp

Slow work returns a Ticket as an explicit handle. Each call authenticates
with its own credential. A loopback call with no Authorization header runs
as the reserved ``operator`` Membership.

Do not add ``from __future__ import annotations`` here. MCPServer injects
``Context`` from the live type annotation.
"""

import inspect
import json
from collections.abc import Callable, Sequence
from typing import Any, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS, ToolAnnotations

from agentconnect.core.base import dump_public
from agentconnect.mcp.actions import (
    TeamRuntime,
    ask_action,
    find_action,
    get_history_action,
    get_result_action,
    resolve_session,
    tell_action,
)
from agentconnect.team.constants import RESERVED_MCP_TOOL_NAMES
from agentconnect.team.errors import TeamError

_INSTRUCTIONS = (
    "You are talking to an AgentConnect Team. Use find to discover teammates "
    "by describing the work. Use ask to send reply-expected work. Use tell "
    "for events. Use get_result to collect a Ticket. Use get_history to page "
    "a conversation. Addresses look like writer or writer@team-name. Keep "
    "ticket.id and thread_id from results. Do not invent thread ids. Pass "
    "idempotency_key when you mean to retry the same ask."
)


def create_team_mcp(
    runtime: TeamRuntime,
    extra_tools: Sequence[Callable[..., Any]] | None = None,
) -> MCPServer:
    """Return the MCP server for ``runtime``.

    Tools are ``find``, ``ask``, ``tell``, ``get_result``, and ``get_history``.
    The roster is the resource ``agentconnect://team/roster``. Extra callables
    are registered by function name and must not reuse a reserved name.

        mcp = create_team_mcp(team)
        async with Client(mcp) as client:
            found = await client.call_tool("find", {"query": "draft a summary"})
    """
    extras = list(
        extra_tools
        if extra_tools is not None
        else list(getattr(runtime, "_extra_tools", []) or [])
    )
    for fn in extras:
        name = getattr(fn, "__name__", "")
        if name in RESERVED_MCP_TOOL_NAMES:
            raise ValueError(f"tool name {name!r} is reserved")

    mcp = MCPServer(
        name=f"agentconnect-{runtime.name}",
        version="1.0.0-draft",
        instructions=_INSTRUCTIONS,
    )

    async def _session(ctx: Context) -> tuple[str, str]:
        try:
            headers = ctx.headers
        except Exception:
            headers = None
        try:
            token = await resolve_session(runtime, headers)
            address = await runtime.caller_address(token)
            return token, address
        except TeamError as exc:
            if exc.code == "unauthorized":
                raise MCPError(INVALID_PARAMS, exc.message) from exc
            raise _tool_error(exc) from exc

    def _rpc_id(ctx: Context) -> str:
        try:
            value = ctx.request_id
        except Exception:
            return ""
        text = str(value)
        if not text or text == "None":
            return ""
        return text

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
        token, _address = await _session(ctx)
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
        deadline_seconds: int,
        wait_seconds: int = 0,
        thread_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send reply-expected work and return a Ticket.

        recipient: Local Address such as "writer".
        content: The work, text or JSON.
        deadline_seconds: How long the recipient has, from 1 to 86400.
        wait_seconds: Local wait from 0 to 30 before returning the current Ticket.
        thread_id: Continue this conversation. Omit to start a new one.
        idempotency_key: Stable key so a retry does not create a second request.
        """
        token, address = await _session(ctx)
        try:
            return await ask_action(
                runtime,
                token,
                address,
                recipient,
                content,
                deadline_seconds=deadline_seconds,
                wait_seconds=wait_seconds,
                thread_id=thread_id,
                idempotency_key=idempotency_key,
                request_id=_rpc_id(ctx),
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
        token, address = await _session(ctx)
        try:
            return await tell_action(
                runtime,
                token,
                address,
                recipient,
                content,
                thread_id=thread_id,
                idempotency_key=idempotency_key,
                request_id=_rpc_id(ctx),
            )
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def get_result(ctx: Context, ticket_id: str) -> dict[str, Any]:
        """Return the current Ticket for work this caller sent.

        ticket_id: Ticket id from ask. Equal to the request Message id.
        """
        token, _address = await _session(ctx)
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
        token, _address = await _session(ctx)
        try:
            return await get_history_action(
                runtime, token, thread_id, before=before, limit=limit
            )
        except ValueError as exc:
            raise MCPError(INVALID_PARAMS, str(exc)) from exc
        except TeamError as exc:
            raise _tool_error(exc) from exc

    async def roster() -> str:
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
    return mcp


def _tool_error(exc: TeamError) -> ToolError:
    payload = {"error": exc.to_error_object()}
    return ToolError(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
