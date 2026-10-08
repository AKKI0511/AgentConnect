"""Scaffold text for ``agentconnect init``."""

from __future__ import annotations

ASSISTANT_PY = '''"""Starter Agent hosted by this Team."""

from __future__ import annotations

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill


class Assistant(BaseAgent):
    """Answers short requests for this Team."""

    profile = AgentProfile(
        summary="Answers short requests for this Team.",
        skills=[
            Skill(
                name="assist",
                description="Reply to a short request with a direct answer.",
            )
        ],
        tags=["assistant"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        return f"Noted: {msg.content}"


def create_assistant(name: str) -> BaseAgent:
    """Build the hosted Assistant and return it unjoined.

    `agentconnect up` calls `create_assistant(name)`. Use a factory when
    the Agent needs constructor arguments the Team file cannot supply.
    Independently deployed Agents skip this file and join by URL with a
    token from `agentconnect token issue`.
    """
    return Assistant(name=name)
'''

AGENTS_INIT_PY = '''"""Hosted Agents for this Team."""
'''

TOOLS_INIT_PY = '''"""Extra MCP tools published by this Team."""
'''

SHARED_PY = '''"""Shared extra tools published on this Team's MCP server."""

from __future__ import annotations


def ping() -> str:
    """Return ``pong`` so callers can check that extra Team MCP tools work."""
    return "pong"
'''
