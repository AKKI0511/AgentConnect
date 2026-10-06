"""Serialized size of model-facing tool views versus wire envelopes."""

from __future__ import annotations

import json
from typing import Any

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.core.base import dump_public
from agentconnect.core.directory import profile_view
from agentconnect.core.operations import history_view, tell_view
from agentconnect.core.ticket import ticket_view
from agentconnect.team import Team


class Writer(BaseAgent):
    """Echoes reply-expected work."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn research notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def handle(self, message, ctx) -> Any:
        if message.kind == "request" and getattr(message, "deadline", None):
            return {"echo": message.content}
        return None


class Coordinator(BaseAgent):
    """Uses Session-bound Team tools."""

    profile = {
        "summary": "Finds teammates and hires them for specialized work.",
        "skills": [
            {
                "name": "research",
                "description": "Find sources and decide who should handle a task.",
            }
        ],
        "tags": ["research"],
    }

    def __init__(self, name: str):
        super().__init__(name=name)
        self.tools = self.team_tools()

    async def handle(self, message, ctx) -> Any:
        return None


class Extra(BaseAgent):
    """Filler Profile for a larger roster measurement."""

    def __init__(self, name: str, index: int):
        super().__init__(
            name=name,
            profile={
                "summary": f"Filler specialist {index} for roster size.",
                "skills": [
                    {
                        "name": f"skill_{index}",
                        "description": f"Placeholder skill {index}.",
                    }
                ],
            },
        )

    async def handle(self, message, ctx) -> Any:
        return None


def _bytes(value: Any) -> int:
    return len(
        json.dumps(
            dump_public(value), separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    )


@pytest.mark.asyncio
async def test_model_facing_views_are_smaller_than_wire_envelopes() -> None:
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Coordinator(name="researcher")
    extras = [Extra(name=f"extra-{index}", index=index) for index in range(8)]
    await writer.join(team)
    await researcher.join(team)
    for extra in extras:
        await extra.join(team)
    try:
        found = await researcher.tools.find(query="draft a summary")
        find_bytes = _bytes(found)
        assert all("agent_did" not in match for match in found["matches"])
        assert all("profile" not in match for match in found["matches"])
        assert len(found["matches"]) == 9
        assert find_bytes < 2500

        entry = await researcher.get_entry("writer")
        profile = await researcher.tools.get_profiles(addresses=["writer"])
        entry_bytes = _bytes(entry)
        profile_bytes = _bytes(profile)
        assert profile["items"][0]["status"] == "ok"
        assert "agent_did" not in profile["items"][0]
        assert profile_bytes < entry_bytes
        assert profile_view(entry).address == entry.address

        several = await researcher.tools.get_profiles(
            addresses=["writer", "writer", extras[0].name]
        )
        assert [item["status"] for item in several["items"]] == ["ok", "ok"]
        several_bytes = _bytes(several)
        one_bytes = profile_bytes
        assert several_bytes < one_bytes * 3
        assert several_bytes > one_bytes

        told = await researcher.tell("writer", {"notice": "changed"})
        tell = await researcher.tools.tell(
            recipient="writer", content={"notice": "changed"}
        )
        tell_bytes = _bytes(tell)
        wire_tell_bytes = _bytes(told)
        assert dump_public(tell_view(told))["status"] == "accepted"
        assert tell["status"] == "accepted"
        assert "message" not in tell
        assert tell_bytes < wire_tell_bytes
        assert tell_bytes < 80

        view = await researcher.tools.ask(
            recipient="writer",
            content="draft this",
            deadline_seconds=30,
        )
        ticket = await researcher.get_result(view["ticket_id"])
        ticket_bytes = _bytes(ticket)
        view_bytes = _bytes(view)
        assert view == dump_public(ticket_view(ticket))
        assert "ttl_ms" not in view
        assert "deadline" not in view
        assert "status_message" not in view
        assert view_bytes < ticket_bytes
        thread_id = view["thread_id"]
        assert thread_id

        history = await researcher.get_history(thread_id)
        history_tool = await researcher.tools.get_history(thread_id=thread_id)
        history_bytes = _bytes(history)
        history_view_bytes = _bytes(history_tool)
        assert history_tool == dump_public(history_view(history))
        assert all("sender_did" not in turn for turn in history_tool["messages"])
        assert all("trace_id" not in turn for turn in history_tool["messages"])
        replies = [
            turn for turn in history_tool["messages"] if turn["kind"] == "response"
        ]
        assert replies
        assert all(turn["parent_id"] == view["ticket_id"] for turn in replies)
        requests = [
            turn for turn in history_tool["messages"] if turn["kind"] == "request"
        ]
        assert all("parent_id" not in turn for turn in requests)
        assert history_view_bytes < history_bytes
        # CPython 3.12.8 local: find 1026; profile 204/275; tell 21/359;
        # completed ticket 155/841; history 383/895 UTF-8 bytes.
    finally:
        await researcher.leave()
        await writer.leave()
        for extra in extras:
            await extra.leave()
        await team.stop()
