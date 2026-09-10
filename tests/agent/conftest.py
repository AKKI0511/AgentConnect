"""Shared helpers for Agent Session tests."""

from __future__ import annotations

import pytest_asyncio

from agentconnect.agent import BaseAgent, Context
from agentconnect.agent.context import DeferredReply
from agentconnect.core.base import JsonValue
from agentconnect.core.message import MailboxMessage
from agentconnect.team import Team


class EchoAgent(BaseAgent):
    """Replies to reply-expected requests by echoing ``content``."""

    async def handle(self, message: MailboxMessage, ctx: Context) -> JsonValue | None:
        if message.kind == "request" and getattr(message, "deadline", None):
            return {"echo": message.content}
        return None


class DeclineAgent(BaseAgent):
    """Reads every Delivery and answers nothing."""

    async def handle(self, message: MailboxMessage, ctx: Context) -> None:
        return None


class BoomAgent(BaseAgent):
    """Raises on every Delivery."""

    async def handle(self, message: MailboxMessage, ctx: Context) -> None:
        raise RuntimeError("handler exploded")


class DeferredAgent(BaseAgent):
    """Takes a Ticket and stores the handle for the test to finish later."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_handle: DeferredReply | None = None
        self.seen: MailboxMessage | None = None

    async def handle(self, message: MailboxMessage, ctx: Context) -> JsonValue | None:
        self.seen = message
        self.ticket_handle = ctx.defer()
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
