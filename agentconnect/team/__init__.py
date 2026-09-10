"""Team runtime: routing, mailboxes, tickets, threads, and directory.

The public type is :class:`~agentconnect.team.runtime.Team`. Start a Team,
join as a member, then talk through ``BaseAgent``. Token-taking methods on
``Team`` are the Session transport.

Hosting adapters (HTTP ASGI, Redis store) are imported from their modules
when you need them:

    from agentconnect.team.http import create_runtime_app
    from agentconnect.team.store import RedisStore
"""

from agentconnect.team.errors import TeamError
from agentconnect.team.runtime import Team

__all__ = [
    "Team",
    "TeamError",
]
