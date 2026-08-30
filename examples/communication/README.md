# Communication examples

Agents subclass ``BaseAgent``, implement ``process_message``, and call ``join``.
The Team never holds Agent objects. Each Agent pulls work through its Session.

```bash
poetry install
poetry run python examples/communication/basic_communication.py
```

`basic_communication.py` starts an embedded Team and two Agents in one process.

`discovery.py` joins a reviewer and a writer, then uses ``find`` to hire
by describing the work. Semantic ranking is on with no extra setup.

`threads.py` continues a conversation with ``thread_id``. The handler reads
``ctx.history``. Older turns are paged with ``get_history``.
``collect="ticket"`` returns a handle; ``collect="wait"`` returns the
terminal Ticket.

`http_session.py` serves the same Team over loopback HTTP. Agents join by URL.
Loopback serving still accepts a join without a token; the Session sends an
identity proof so the Runtime can stamp the Agent DID.

`tools.py` uses ``team_tools()`` so a coordinator finds a writer and asks
without hardcoding an Address. Same five tools as the Team MCP server.

`mcp.py` serves the Team and prints ``team.mcp_url`` for Cursor MCP config.

`join_auth.py` starts a Team with ``require_join_auth=True``. The operator
issues a token bound to one Agent DID. A different Agent cannot use it.

```python
issued = await team.issue_join_token(name="writer", agent_did=writer.agent_did)
await Writer(name="writer").join(url, join_token=issued["token"])
```

```bash
poetry run python examples/communication/discovery.py
poetry run python examples/communication/tools.py
poetry run python examples/communication/http_session.py
poetry run python examples/communication/join_auth.py
poetry run python examples/communication/threads.py
poetry run python examples/communication/mcp.py
```

A handler can return a value (reply), return nothing (decline a request, or
finish an event), raise (fail the request), or call ``ctx.ticket()`` and answer
later. ``join`` retries while the Team is coming up and reconnects if the Team
restarts.
