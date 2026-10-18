# Team MCP

Connect an existing MCP harness to `team.mcp_url` after `Team.serve()` starts the
listener. The harness installs the advertised tools into its model. Python
harnesses without MCP can adapt the descriptors from `BaseAgent.team_tools()`;
those descriptors are bound to the Agent Session.

The six Team tools are `find`, `get_profiles`, `ask`, `tell`, `get_result` and
`get_history`. The roster is `agentconnect://team/roster`.

`ask` returns a TicketView. Keep `ticket_id` while it is open and collect with
`get_result`. Completed views carry content alone; failed or expired views
carry an error, and a decline has neither. `tell` acknowledges queued delivery,
which does not mean the recipient finished handling it. Continue a Thread only
with its original participants. History pages arrive newest first, with turns
in ascending sequence inside each page; use `next_before` to read older pages.

Calls, extra tools and resource reads require a live Session bearer. A join
invitation cannot substitute for a Session token. Direct trusted loopback calls
without Authorization use the operator Membership. Proxied calls require a
bearer, including proxies in front of a loopback listener. Present empty or
malformed Authorization and forwarded-client headers never grant operator access.

For custom hosting, `create_team_mcp` builds a Server for an already started
Team. It starts no listener. Disable `in_process` for HTTP hosts; the host owns
serving and cleanup. Extra callables use their function names and cannot reuse
reserved or duplicate names. Omitting `extra_tools` uses the Team's configured
tools; an empty list publishes none.

See the [server reference](../../docs-v2/api/mcp-server.mdx),
[HTTP hosting contract](../../docs-v2/api/team-http.mdx) and
[MCP binding](../../spec/bindings/mcp.md).
