"""Shared helpers for Agent Session tests."""

from __future__ import annotations

from typing import Any

import pytest_asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class EchoAgent(BaseAgent):
    """Replies to reply-expected requests by echoing ``content``."""

    async def process_message(self, message, ctx) -> Any:
        if message.kind == "request" and getattr(message, "deadline", None):
            return {"echo": message.content}
        return None


class DeclineAgent(BaseAgent):
    """Reads every Delivery and answers nothing."""

    async def process_message(self, message, ctx) -> None:
        return None


class BoomAgent(BaseAgent):
    """Raises on every Delivery."""

    async def process_message(self, message, ctx) -> None:
        raise RuntimeError("handler exploded")


class DeferredAgent(BaseAgent):
    """Takes a Ticket and stores the handle for the test to finish later."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handle = None
        self.seen = None

    async def process_message(self, message, ctx):
        self.seen = message
        self.handle = ctx.ticket()
        return None


@pytest_asyncio.fixture(loop_scope="function")
async def team():
    runtime = Team(
        "content-squad",
        session_ttl_seconds=30,
        lease_ttl_seconds=10,
        sweep_interval_seconds=0.05,
    )
    await runtime.start()
    try:
        yield runtime
    finally:
        await runtime.stop()
