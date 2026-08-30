Team MCP
========

.. _discovery_mcp:

One MCP server per Team. ``Team.serve()`` mounts it at ``{origin}/mcp``. Cursor,
Claude, and any other MCP client talk to that URL. Python hosts that do not
speak MCP use :meth:`BaseAgent.team_tools() <agentconnect.agent.base.BaseAgent.team_tools>`
instead.

.. admonition:: At a glance
   :class: tip

   - ``await team.serve()`` then add ``team.mcp_url`` to the MCP client.
   - Tools are ``find``, ``ask``, ``tell``, ``get_result``, and ``get_history``.
   - Slow work returns a Ticket. Keep ``ticket.id``.
   - Loopback calls with no ``Authorization`` header run as ``operator``.

Serve and connect
-----------------

.. code-block:: python

    from agentconnect.agent import BaseAgent
    from agentconnect.team import Team

    class Writer(BaseAgent):
        profile = {
            "summary": "Writes short drafts from notes.",
            "skills": [{"name": "drafting", "description": "Turn notes into a draft."}],
        }

        async def process_message(self, msg, ctx):
            return f"Draft complete for {msg.get('content')!r}."

    team = await Team("content-squad").start()
    await Writer(name="writer").join(team)
    await team.serve()
    print(team.mcp_url)

Cursor MCP config (``.cursor/mcp.json``):

.. code-block:: json

    {
      "mcpServers": {
        "content-squad": {
          "url": "http://127.0.0.1:9000/mcp"
        }
      }
    }

Replace the port with the one ``team.mcp_url`` printed.

Tools
-----

``find`` ranks teammates from a natural-language query. ``ask`` sends
reply-expected work and returns a Ticket. ``tell`` sends an event.
``get_result`` rereads a Ticket. ``get_history`` pages a Thread.

The roster is the resource ``agentconnect://team/roster``.

Authentication
--------------

Pass ``Authorization: Bearer <session_token>`` to run as that member. Omit
the header on loopback to run as ``operator``. A bad Bearer token is an MCP
error. It is never treated as the operator.

Session-bound callables
-----------------------

.. code-block:: python

    class Coordinator(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.tools = self.team_tools()

        async def process_message(self, msg, ctx):
            found = await self.tools.find(query=str(msg["content"]))
            return await self.tools.ask(
                recipient=found["matches"][0]["address"],
                content=msg["content"],
                deadline_seconds=30,
                wait_seconds=10,
            )

See ``examples/communication/mcp.py`` and ``examples/communication/tools.py``.
