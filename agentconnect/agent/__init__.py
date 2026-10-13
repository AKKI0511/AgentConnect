"""Connect your agent's harness to a Team and respond to teammates.

Subclass `BaseAgent` and implement `handle` to pass incoming work to
your harness. Join a started `Team` or its served URL. When a teammate
sends a request or event, `handle` receives a `MailboxMessage` and a
`Context` for that delivery. Return a reply to a request, or use the
Context to ask another teammate while handling it.
"""

from agentconnect.agent.base import BaseAgent
from agentconnect.agent.context import Context, DeferredReply
from agentconnect.agent.errors import SessionError

__all__ = [
    "BaseAgent",
    "Context",
    "DeferredReply",
    "SessionError",
]
