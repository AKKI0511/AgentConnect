"""Threads, history paging, and collect=wait past the Runtime hold."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.agent import SessionError
from agentconnect.team import Team
from tests.agent.conftest import DeferredAgent, EchoAgent


@pytest.mark.asyncio
async def test_ask_wait_polls_until_terminal_after_hold():
    runtime = Team("content-squad", wait_hold_seconds=0.05, session_ttl_seconds=30)
    await runtime.start()
    writer = DeferredAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        task = asyncio.create_task(
            researcher.ask("writer", "later", deadline_seconds=8, collect="wait")
        )
        for _ in range(50):
            if writer.handle is not None:
                break
            await asyncio.sleep(0.05)
        assert writer.handle is not None
        await writer.handle.reply("done after hold")
        result = await asyncio.wait_for(task, timeout=5)
        assert result["ticket"]["state"] == "completed"
        assert result["ticket"]["response"]["content"] == "done after hold"
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_threaded_ask_exposes_history_and_paging(team: Team):
    class Historian(EchoAgent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.seen_history = None

        async def process_message(self, message, ctx):
            self.seen_history = list(ctx.history)
            if message.kind == "request" and getattr(message, "deadline", None):
                return {"echo": message.content, "prior": len(ctx.history)}
            return None

    writer = Historian(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        thread_id = str(uuid.uuid4())
        first = await researcher.ask(
            "writer", "turn-0", deadline_seconds=5, thread_id=thread_id
        )
        assert first["ticket"]["state"] == "completed"
        second = await researcher.ask(
            "writer", "turn-1", deadline_seconds=5, thread_id=thread_id
        )
        assert second["ticket"]["response"]["content"]["prior"] >= 1
        assert writer.seen_history is not None
        assert writer.seen_history[0]["content"] == "turn-0"
        page = await researcher.get_history(thread_id, limit=10)
        kinds = [msg["kind"] for msg in page["messages"]]
        assert "request" in kinds
        assert "response" in kinds
        missing = await researcher.get_history(thread_id, before=str(uuid.uuid4()))
        assert [msg["id"] for msg in missing["messages"]] == [
            msg["id"] for msg in page["messages"]
        ]
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_unsupported_collect_fails_loudly(team: Team):
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        with pytest.raises(SessionError) as exc:
            await researcher.ask(
                "writer",
                "nope",
                deadline_seconds=5,
                collect="stream",
            )
        assert exc.value.code == "unsupported_collect_mode"
    finally:
        await writer.leave()
        await researcher.leave()


@pytest.mark.asyncio
async def test_ids_history_exposes_history_ids(team: Team):
    class IdWriter(EchoAgent):
        def __init__(self):
            super().__init__(name="writer", delivery_history="ids")
            self.seen_ids = None
            self.seen_history = None

        async def process_message(self, message, ctx):
            self.seen_ids = ctx.history_ids
            self.seen_history = list(ctx.history)
            if message.kind == "request" and getattr(message, "deadline", None):
                return {
                    "echo": message.content,
                    "prior_ids": list(ctx.history_ids or []),
                }
            return None

    writer = IdWriter()
    researcher = EchoAgent(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        thread_id = str(uuid.uuid4())
        await researcher.ask(
            "writer", "turn-0", deadline_seconds=5, thread_id=thread_id
        )
        second = await researcher.ask(
            "writer", "turn-1", deadline_seconds=5, thread_id=thread_id
        )
        assert writer.seen_history == []
        assert writer.seen_ids
        assert second["ticket"]["response"]["content"]["prior_ids"]
        page = await researcher.get_history(thread_id, limit=10)
        assert page["messages"]
    finally:
        await writer.leave()
        await researcher.leave()
