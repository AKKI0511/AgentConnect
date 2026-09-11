"""Harnesses that run inside ``BaseAgent.handle``.

The Team never calls a model. ``handle`` is the adapter, the way
``forward`` is the adapter in PyTorch. Swap the harness without
changing join, ``ask``, or Tickets.

``StubHarness`` is the default. It does not call a provider.
``OpenAIHarness`` is live Chat Completions. Missing credentials fail
with setup text instead of falling back to the stub.
"""

from __future__ import annotations

import asyncio
import os
from typing import Protocol

from agentconnect.core.message import Message

LIVE_SETUP = """\
Live mode needs an OpenAI API key.

1. Copy .env.example to .env in this folder
2. Set OPENAI_API_KEY
3. Run: uv run python -m team_demo --live

Optional: OPENAI_MODEL (default gpt-4o-mini)
Optional: OPENAI_BASE_URL for a compatible endpoint
"""

RESEARCH_NOTES = (
    "AgentConnect is a messaging runtime for independent agents.\n"
    "Each specialist keeps its own models and tools.\n"
    "Outstanding work is a Ticket the Team holds."
)

LAUNCH_DRAFT = f"Launch note: {RESEARCH_NOTES}"


class Harness(Protocol):
    """One specialist's private execution path."""

    async def complete(
        self,
        *,
        instructions: str,
        task: str,
        notes: str,
        history: list[Message],
    ) -> str:
        """Return the specialist's reply text."""


class StubHarness:
    """Fixed replies so the Team path runs without a provider.

    Writer and researcher pass a ``role``. ``delay_seconds`` holds the
    call so tests can outlast a wait hold without a live model.
    """

    def __init__(self, role: str, *, delay_seconds: float = 0.0) -> None:
        self.role = role
        self.delay_seconds = delay_seconds

    async def complete(
        self,
        *,
        instructions: str,
        task: str,
        notes: str,
        history: list[Message],
    ) -> str:
        del instructions, task, history
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.role == "researcher":
            return RESEARCH_NOTES
        return LAUNCH_DRAFT if not notes else f"Launch note: {notes}"


class OpenAIHarness:
    """OpenAI Chat Completions inside ``handle``.

    Thread history from the Team is passed as prior turns. Private
    memory stays in this process; AgentConnect does not store it.
    """

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise SystemExit(LIVE_SETUP)
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
        self._client = AsyncOpenAI()

    async def complete(
        self,
        *,
        instructions: str,
        task: str,
        notes: str,
        history: list[Message],
    ) -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": instructions}]
        for item in history:
            role = "assistant" if item.kind == "response" else "user"
            messages.append({"role": role, "content": message_text(item)})
        user = task if not notes else f"{task}\n\nResearch notes:\n{notes}"
        messages.append({"role": "user", "content": user})
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        text = response.choices[0].message.content
        if not text:
            raise RuntimeError("The model returned an empty reply.")
        return text


def _as_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return str(value)


def message_text(item: Message) -> str:
    """Return a Message body as text. Error messages have no content field."""
    content = getattr(item, "content", None)
    if content is None:
        return item.kind
    return _as_text(content)
