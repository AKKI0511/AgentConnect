"""Start a Team and talk to it as the operator.

Install the CLI extra (`agentconnect[cli]`). Use the `agentconnect` script
or `python -m agentconnect.cli`.

Foreground `up` occupies the terminal until interrupted. Run other commands
from a second terminal, or use `up --detach`, which returns before the
Runtime is ready.

Origin selection is `--url`, then `--file`, then saved `up` state, then a
discovered Team file, then loopback port 9000. A missing or invalid `--file`
fails. Revoking a join token drops Sessions created from it; it does not
stop an OS process. Run `--help` on a command for complete options.

| Command | Outcome |
| --- | --- |
| `agentconnect init` | Writes `agentconnect.toml`, `agents/assistant.py`, and `tools/shared.py`. |
| `agentconnect up` | Starts the Runtime and hosted Agents. |
| `agentconnect down` | Stops the process this CLI started for that Team file. |
| `agentconnect status` | Members, online state, Mailbox depths, and open Tickets. |
| `agentconnect token issue` | Prints a join token secret, then `expires_at`. |
| `agentconnect token revoke TOKEN` | Revokes the token and drops Sessions created from it. |
| `agentconnect find QUERY` | Ranked Directory matches. |
| `agentconnect ask ADDRESS QUESTION` | Sends reply-expected work and waits. The wait can end with an open Ticket. |
| `agentconnect trace TRACE_ID` | Timeline for one causal operation. |
| `agentconnect watch` | Prints new Trace events until interrupted. |
| `agentconnect doctor` | Checks the Team file, selected origin, and Runtime access. |
| `agentconnect version` | Prints the installed package version. |
"""
