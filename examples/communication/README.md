# Communication examples

Agents subclass ``BaseAgent``, implement ``handle``, and call ``join``.
The Team never holds Agent objects. Each Agent pulls work through its Session.

```bash
poetry install
poetry run python examples/communication/basic_communication.py
```

`basic_communication.py` starts an embedded Team and two Agents in one process.
After they talk, it prints ``status`` so you can see which members are online.

`discovery.py` joins a reviewer and a writer, then uses ``find`` to hire
by describing the work. Semantic ranking is on with no extra setup.

`threads.py` continues a conversation with ``thread_id``. The handler reads
``ctx.history``. Older turns are paged with ``get_history``, ordered by
per-Thread ``seq``. ``collect="ticket"`` returns a handle; ``collect="wait"``
returns the terminal Ticket.

`history_ids.py` joins the writer with ``delivery_history="ids"``. Each
Delivery carries earlier Message ids on ``ctx.history_ids`` and leaves
``ctx.history`` empty. Page bodies with ``get_history`` when you need them.

`http_session.py` serves the same Team over loopback HTTP. Agents join by URL.
Loopback serving still accepts a join without a token; the Session sends an
identity proof so the Runtime can stamp the Agent DID.

`tools.py` uses ``team_tools()`` so a coordinator finds a writer and asks
without hardcoding an Address. Same five tools as the Team MCP server.

`mcp.py` serves the Team and prints ``team.mcp_url`` for Cursor MCP config.

`hosted_team/` is a Team file. From that directory, ``agentconnect up``
starts the Runtime and joins ``Writer``. ``agentconnect ask`` and
``agentconnect trace`` then talk to it as the operator.

`trace.py` fails a request on purpose, then prints the Trace timeline.
Each event may carry ``parent_id`` of the Message it names.

`aiagent.py` is a model-backed Agent. It uses a recorded model by default
so it runs without an API key. Set ``AGENTCONNECT_MODEL`` to use LiteLLM.

```bash
poetry run python examples/communication/aiagent.py
```

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
poetry run python examples/communication/trace.py
```

From ``examples/communication/hosted_team``::

    poetry run agentconnect up


A handler can return a value (reply), return nothing (decline a request, or
finish an event), raise (fail the request), or call ``ctx.ticket()`` and answer
later. ``join`` retries while the Team is coming up and reconnects if the Team
restarts.
