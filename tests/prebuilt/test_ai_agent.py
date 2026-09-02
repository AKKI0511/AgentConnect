"""Golden tests for AIAgent on a recorded model."""

from __future__ import annotations

from typing import Any

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.prebuilt import AIAgent, Tool
from agentconnect.team import Team
from tests.prebuilt.test_loop import scripted, text_turn, tool_turn


class Writer(BaseAgent):
    """Returns a fixed draft."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def process_message(self, message, ctx) -> Any:
        if message.kind != "request":
            return None
        return "Draft complete."


@pytest.mark.asyncio
async def test_aiagent_chat_uses_recorded_model():
    agent = AIAgent(
        name="assistant",
        model="recorded",
        complete=scripted(text_turn("a Ticket is a durable result record")),
    )
    reply = await agent.chat("What is a Ticket?")
    assert "Ticket" in reply


@pytest.mark.asyncio
async def test_aiagent_chat_keeps_conversation_history():
    complete = scripted(
        text_turn("first"),
        text_turn("second with memory"),
    )
    agent = AIAgent(name="assistant", model="recorded", complete=complete)
    assert await agent.chat("one", conversation_id="t") == "first"
    assert await agent.chat("two", conversation_id="t") == "second with memory"
    assert [item["role"] for item in agent._chats["t"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_aiagent_process_message_reads_ctx_history():
    recorded: list[list[dict[str, Any]]] = []
    turns = [text_turn("first reply"), text_turn("second reply")]

    async def complete(**kwargs):
        recorded.append(list(kwargs["messages"]))
        return turns.pop(0)

    class Silent(BaseAgent):
        async def process_message(self, message, ctx) -> Any:
            return None

    team = await Team("content-squad").start()
    asker = Silent(name="asker")
    agent = AIAgent(name="researcher", model="recorded", complete=complete)
    await asker.join(team)
    await agent.join(team)
    try:
        thread_id = "11111111-1111-1111-1111-111111111111"
        first = await asker.ask("researcher", "one", thread_id=thread_id)
        second = await asker.ask("researcher", "two", thread_id=thread_id)
        assert first["ticket"]["response"]["content"] == "first reply"
        assert second["ticket"]["response"]["content"] == "second reply"
        assert len(recorded) == 2
        second_contents = [str(item.get("content")) for item in recorded[1]]
        assert any("one" in content for content in second_contents)
        assert any("first reply" in content for content in second_contents)
    finally:
        await agent.leave()
        await asker.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_aiagent_team_tools_find_without_hardcoded_address():
    complete = scripted(
        tool_turn("find", '{"query": "someone who can draft a summary"}'),
        text_turn("writer can draft"),
    )
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = AIAgent(name="researcher", model="recorded", complete=complete)
    await writer.join(team)
    await researcher.join(team)
    try:
        result = await writer.ask("researcher", "who can draft?")
        ticket = result["ticket"]
        assert ticket["state"] == "completed"
        assert "writer" in str(ticket["response"]["content"])
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_aiagent_custom_tool_runs_in_loop():
    async def search_docs(query: str) -> str:
        return f"hit:{query}"

    complete = scripted(
        tool_turn("search_docs", '{"query": "tickets"}'),
        text_turn("found tickets"),
    )
    agent = AIAgent(
        name="researcher",
        model="recorded",
        complete=complete,
        tools=[
            Tool(
                name="search_docs",
                description="Search docs.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                handler=search_docs,
            )
        ],
    )
    reply = await agent.chat("search tickets")
    assert reply == "found tickets"


def test_aiagent_requires_model():
    with pytest.raises(ValueError, match="model is required"):
        AIAgent(name="assistant", model="  ")


def test_recorded_complete_does_not_import_litellm():
    import sys

    for name in list(sys.modules):
        if name == "litellm" or name.startswith("litellm."):
            sys.modules.pop(name, None)
    AIAgent(
        name="assistant",
        model="recorded",
        complete=scripted(text_turn("ok")),
    )
    loaded = [
        name for name in sys.modules if name == "litellm" or name.startswith("litellm.")
    ]
    assert loaded == []
