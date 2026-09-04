"""Scaffold text for ``agentconnect init``."""

from __future__ import annotations

ASSISTANT_PY = '''"""Starter Agent created by ``agentconnect init``."""

from __future__ import annotations

from typing import Any

from agentconnect.agent import BaseAgent


class Assistant(BaseAgent):
    """Echoes reply-expected work so a fresh Team can be asked immediately.

    .. code-block:: python

        await Assistant(name="assistant").join(team)
    """

    profile = {
        "summary": "Handles short tasks and returns a plain reply.",
        "skills": [
            {
                "name": "assist",
                "description": "Read a request and return a short answer.",
            }
        ],
        "tags": ["assistant"],
    }

    async def handle(self, msg: Any, ctx: Any) -> Any:
        """Reply to a request with the received content."""
        if getattr(msg, "kind", None) != "request":
            return None
        return {"echo": getattr(msg, "content", None)}
'''

AGENTS_INIT_PY = '''"""Hosted Agents for this Team."""
'''
