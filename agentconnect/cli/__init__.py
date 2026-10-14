"""Console entry `agentconnect`: start a Team and talk to it as a person.

`app` is the Typer application installed as the `agentconnect` script.
A person is a client of the Team, like any Agent, over loopback HTTP as
the reserved `operator` Membership.

Commands that exist today: `init`, `up`, `down`, `status`, `token issue`,
`token revoke`, `find`, `ask`, `trace`, `watch`, `doctor`, `version`.
This is a subset of the SDK and of Team MCP. Hosted Agents in the Team
file are constructed only at `up`. `up --detach` starts the process; it
does not wait until the Runtime is ready. `down` stops the process this
CLI started. Revoking a join token or removing a Membership does not
kill an Agent process you did not start.

Origin selection is `--url`, then `--file`, then saved `up` state,
then the nearest Team file, then loopback port 9000. A missing or
invalid `--file` fails rather than choosing another Team.

Examples:
    Scaffold and start from a shell:

    ```bash
    agentconnect init
    agentconnect up
    agentconnect status
    agentconnect down
    ```
"""

from .main import app

__all__ = ["app"]
