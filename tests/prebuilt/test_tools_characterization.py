"""Characterization of the tool surface the prebuilt loop sees.

Pins ``Tool``, ``_call_tool``, and ``AIAgent`` tool advertising.
No network and no litellm.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

import pytest

from agentconnect.agent import BaseAgent, TeamTools, Tool
from agentconnect.agent.tools import _call_tool
from agentconnect.prebuilt import AIAgent
from agentconnect.prebuilt.loop import ToolLoopExhausted
from agentconnect.team import Team
from tests.prebuilt.test_loop_characterization import scripted, text_turn, tool_turn


def test_tool_openai_schema_shape():
    tool = Tool(
        name="ping",
        description="Return pong.",
        parameters={"type": "object", "properties": {}},
        handler=lambda: "pong",
    )
    assert tool.openai_schema() == {
        "type": "function",
        "function": {
            "name": "ping",
            "description": "Return pong.",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def test_plain_annotated_function_registers_without_handwritten_schema():
    async def search_docs(query: str) -> str:
        """Search internal docs.

        Args:
            query: The search text.
        """
        return f"no hits for {query}"

    tool = Tool.from_callable(search_docs)
    assert tool.name == "search_docs"
    assert tool.description == "Search internal docs."
    assert tool.parameters["type"] == "object"
    assert "query" in tool.parameters["properties"]
    assert (
        tool.parameters["properties"]["query"].get("description") == "The search text."
    )
    assert tool.parameters.get("required") == ["query"]


def test_explicit_schema_escape_hatch_keeps_handwritten_parameters():
    async def dynamic(**kwargs: Any) -> str:
        return json.dumps(kwargs)

    tool = Tool(
        name="dynamic",
        description="Schema annotations cannot express.",
        parameters={
            "type": "object",
            "properties": {
                "payload": {"type": "object", "additionalProperties": True},
            },
            "required": ["payload"],
        },
        handler=dynamic,
    )
    assert tool.parameters["properties"]["payload"]["additionalProperties"] is True


@pytest.mark.asyncio
async def test_call_tool_invokes_once_and_stringifies_results():
    seen: list[dict[str, Any]] = []

    async def echo(value: str) -> str:
        seen.append({"value": value})
        return f"got:{value}"

    tool = Tool(
        name="echo",
        description="Echo.",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        handler=echo,
    )
    assert await _call_tool(tool, '{"value": "hi"}') == "got:hi"
    assert seen == [{"value": "hi"}]

    async def as_dict() -> dict[str, str]:
        return {"ok": True}

    async def as_none() -> None:
        return None

    assert await _call_tool(
        Tool(
            name="d",
            description="",
            parameters={"type": "object", "properties": {}},
            handler=as_dict,
        ),
        "{}",
    ) == json.dumps({"ok": True})
    assert (
        await _call_tool(
            Tool(
                name="n",
                description="",
                parameters={"type": "object", "properties": {}},
                handler=as_none,
            ),
            "{}",
        )
        == "null"
    )


@pytest.mark.asyncio
async def test_call_tool_typeerror_handler_is_invoked_once():
    invocations: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def always_typeerror(*args: Any, **kwargs: Any) -> str:
        invocations.append((args, kwargs))
        raise TypeError("boom")

    tool = Tool(
        name="broken",
        description="Raises TypeError.",
        parameters={"type": "object", "properties": {}},
        handler=always_typeerror,
    )
    with pytest.raises(TypeError, match="boom"):
        await _call_tool(tool, "{}")
    assert len(invocations) == 1


@pytest.mark.asyncio
async def test_call_tool_passes_advertised_names_as_keywords():
    seen: list[dict[str, Any]] = []

    async def take(payload: dict[str, str]) -> str:
        seen.append(payload)
        return payload["value"]

    tool = Tool.from_callable(take)
    assert await _call_tool(tool, {"payload": {"value": "hi"}}) == "hi"
    assert seen == [{"value": "hi"}]
    with pytest.raises(ValidationError):
        await _call_tool(tool, {"value": "hi"})
    assert seen == [{"value": "hi"}]


@pytest.mark.asyncio
async def test_team_tools_items_are_tools_and_include_get_profile():
    class Holder(BaseAgent):
        async def handle(self, message, ctx) -> Any:
            return None

    agent = Holder(name="holder")
    team_tools = agent.team_tools()
    assert isinstance(team_tools, TeamTools)
    assert [item.name for item in team_tools] == [
        "find",
        "ask",
        "tell",
        "get_result",
        "get_history",
        "get_profile",
    ]
    for item in team_tools:
        assert isinstance(item, Tool)


@pytest.mark.asyncio
async def test_aiagent_chat_does_not_attach_team_tools():
    recorded: list[dict[str, Any]] = []

    async def complete(**kwargs: Any) -> Any:
        recorded.append(kwargs)
        return text_turn("ok")

    team = await Team("content-squad").start()
    peer = BaseAgent(name="peer")
    agent = AIAgent(name="assistant", model="recorded", complete=complete)
    await peer.join(team)
    await agent.join(team)
    try:
        reply = await agent.chat("hello")
        assert reply == "ok"
        assert len(recorded) == 1
        assert "tools" not in recorded[0]
    finally:
        await agent.leave()
        await peer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_aiagent_complete_advertises_team_tools_and_custom_override():
    recorded: list[dict[str, Any]] = []

    async def complete(**kwargs: Any) -> Any:
        recorded.append(kwargs)
        return text_turn("ok")

    async def custom_find(query: str) -> str:
        return f"custom:{query}"

    custom = Tool(
        name="find",
        description="Custom find.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=custom_find,
    )
    extra = Tool(
        name="search_docs",
        description="Search docs.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=custom_find,
    )

    team = await Team("content-squad").start()
    peer = BaseAgent(name="peer")
    agent = AIAgent(
        name="assistant",
        model="recorded",
        complete=complete,
        include_team_tools=True,
        tools=[custom, extra],
    )
    await peer.join(team)
    await agent.join(team)
    try:
        reply = await agent.complete("hello", include_team_tools=True)
        assert reply == "ok"
        schemas = recorded[0]["tools"]
        names = [item["function"]["name"] for item in schemas]
        assert names == [
            "find",
            "ask",
            "tell",
            "get_result",
            "get_history",
            "get_profile",
            "search_docs",
        ]
        find_schema = next(
            item for item in schemas if item["function"]["name"] == "find"
        )
        assert find_schema["function"]["description"] == "Custom find."
    finally:
        await agent.leave()
        await peer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_aiagent_accepts_plain_function_in_tools_list():
    recorded: list[dict[str, Any]] = []

    async def complete(**kwargs: Any) -> Any:
        recorded.append(kwargs)
        return text_turn("ok")

    async def search_docs(query: str) -> str:
        """Search docs."""
        return query

    agent = AIAgent(
        name="assistant",
        model="recorded",
        complete=complete,
        include_team_tools=False,
        tools=[search_docs],
    )
    await agent.complete("hello", include_team_tools=False)
    names = [item["function"]["name"] for item in recorded[0]["tools"]]
    assert names == ["search_docs"]


@pytest.mark.asyncio
async def test_completed_ask_tool_result_is_ticket_view():
    """Model-facing ask returns TicketView, not dump_public(Ticket)."""

    class Writer(BaseAgent):
        profile = {
            "summary": "Writes short drafts from notes.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Turn notes into a draft.",
                }
            ],
        }

        async def handle(self, message, ctx) -> Any:
            if message.kind == "request":
                return {"echo": message.content}
            return None

    class Coordinator(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.tools = self.team_tools()

        async def handle(self, message, ctx) -> Any:
            return None

    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Coordinator(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.tools.ask(
            recipient="writer",
            content="draft this",
            deadline_seconds=30,
        )
        assert ticket["state"] == "completed"
        assert "ticket_id" in ticket
        assert "ttl_ms" in ticket
        assert ticket["status_message"] == "Completed."
        assert ticket["content"] == {"echo": "draft this"}
        bookkeeping = {
            "id",
            "requester",
            "recipient",
            "trace_id",
            "created_at",
            "updated_at",
            "late_reply_count",
            "response",
            "sender_did",
            "seq",
        }
        assert bookkeeping.isdisjoint(ticket.keys())
        assert isinstance(ticket["ttl_ms"], int)
        assert ticket["ttl_ms"] >= 0
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_get_profile_returns_one_full_entry_while_find_summary_stays_light():
    class Writer(BaseAgent):
        profile = {
            "summary": "Writes short drafts from notes.",
            "description": "Longer drafting Profile used only on full reads.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Turn notes into a draft.",
                    "tags": ["writing"],
                }
            ],
            "tags": ["writing"],
        }

        async def handle(self, message, ctx) -> Any:
            return None

    class Coordinator(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.tools = self.team_tools()

        async def handle(self, message, ctx) -> Any:
            return None

    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Coordinator(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        found = await researcher.tools.find(query="draft a summary")
        match = next(
            item for item in found["matches"] if item["address"].startswith("writer@")
        )
        assert "profile" not in match
        assert "agent_did" not in match
        assert "description" not in match
        entry = await researcher.tools.get_profile(address="writer")
        assert entry["address"].startswith("writer@")
        assert entry["profile"]["description"].startswith("Longer drafting")
        assert entry["profile"]["skills"][0]["tags"] == ["writing"]
        assert "agent_did" in entry
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_exhaustion_does_not_return_success_string_from_loop_or_chat():
    async def ping() -> str:
        return "pong"

    ping_tool = Tool(
        name="ping",
        description="Return pong.",
        parameters={"type": "object", "properties": {}},
        handler=ping,
    )
    agent = AIAgent(
        name="assistant",
        model="recorded",
        complete=scripted(
            tool_turn("ping", "{}", content="keep going"),
            tool_turn("ping", "{}", "c2", content="still going"),
        ),
        tools=[ping_tool],
        include_team_tools=False,
        max_tool_rounds=2,
    )
    with pytest.raises(ToolLoopExhausted):
        await agent.chat("loop")
