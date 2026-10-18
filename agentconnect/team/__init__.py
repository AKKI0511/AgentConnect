"""Run the Team your agents use to work together.

Agents on a Team find teammates, ask them for work, and collect replies.
Each agent keeps its own harness. Start a `Team` before they join.

An agent in this process joins the Team object. An agent on the same
machine joins the loopback origin from `Team.serve`. An agent on another
host needs the app from `create_runtime_app`, on a server you run.

A failed Team operation raises `TeamError`. Read its `code`.
"""

from agentconnect.team.errors import TeamError
from agentconnect.team.runtime import Team

__all__ = [
    "Team",
    "TeamError",
]
