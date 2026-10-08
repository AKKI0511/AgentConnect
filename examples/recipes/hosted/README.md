# Hosted Team from a file

`agentconnect.toml` names the Team and the Agents this process hosts.
`class` is a `BaseAgent` subclass or a function `create(name)` that
returns an unjoined Agent. `agentconnect up` starts the Runtime and
joins those Agents.

From this directory, using the recipes uv project::

    uv run --project .. agentconnect up

In another terminal, from this directory::

    uv run --project .. agentconnect find "someone who can draft a summary"
    uv run --project .. agentconnect ask writer "Draft two paragraphs about the launch."

`ask` prints the `trace_id`. `agentconnect trace` prints accept, lease,
and reply.

Independently deployed Agents are not listed in the file. Issue a token
and join by URL::

    uv run --project .. agentconnect token issue --name researcher

Then `Researcher(name="researcher").join(url, join_token=...)` from
another process.

`tools` in the Team file publishes extra callables on Team MCP.
Connecting a harness is a separate step: add `{origin}/mcp` there.
Joining does not attach those extras to a model's tool list.

`up` binds loopback only. For authenticated or non-loopback serving,
build the ASGI app with `create_runtime_app(team)` from
`agentconnect.team.http`.
