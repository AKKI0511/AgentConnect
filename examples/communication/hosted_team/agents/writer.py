"""Hosted Writer started by ``agentconnect up``."""

from __future__ import annotations

from typing import Any

from agentconnect.agent import BaseAgent


class Writer(BaseAgent):
    """Turns a request into a short draft.

    .. code-block:: python

        await Writer(name="writer").join(team)
    """

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

    async def process_message(self, msg, ctx) -> Any:
        """Reply to a request with a draft line."""
        if msg.kind != "request":
            return None
        return f"Draft complete for {msg.content!r}."
