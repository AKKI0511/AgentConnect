# Hosted Team from a file

`agentconnect.yaml` names the Team and the Agent classes this process
hosts. `agentconnect up` starts the Runtime and joins those Agents.

From this directory, using the recipes uv project::

    uv run --project .. agentconnect up

In another terminal, from this directory::

    uv run --project .. agentconnect find "someone who can draft a summary"
    uv run --project .. agentconnect ask writer "Draft two paragraphs about the launch."

`ask` prints the `trace_id`. `agentconnect trace` prints accept, lease,
and reply.

Network Agents join this Team with a token::

    uv run --project .. agentconnect token issue --name researcher
