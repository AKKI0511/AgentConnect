Discovery MCP
==============

.. _discovery_mcp:

Prerequisites
--------------

Complete :doc:`../../../installation` first. Read :doc:`../../core_concepts` for the mental
model, then :doc:`../../core/discovery/discovery_registry_remote` to stand up a Registry API
server and register agents to it. The Discovery MCP server sits directly on top of that
server.

What Discovery MCP Does
------------------------

Discovery MCP lets any MCP-compatible client (Cursor, Claude Desktop, Claude Code, Codex,
or a custom client on the MCP SDK) search your agent network with a plain language
description and get back a ranked list of agents, with no AgentConnect import required on
that client.

.. admonition:: At a glance
   :class: tip

   - Start it with ``agentconnect mcp start agent-discovery``. It talks to your existing
     Registry API server. Nothing else to run.
   - Your MCP client launches it directly. There is no address or port to configure.
   - It exposes one tool, ``search_for_agents``, for natural language capability search.
   - Defaults for result count, match strictness, and detail level live in
     ``agentconnect.yaml``.

From a Hub to Agents Anyone Can Find
-------------------------------------

Agents registered to an in-process ``AgentRegistry`` are visible only to code running in
that same process. MCP discovery reaches a different registry: the standalone Registry API
server, accessed over HTTP through ``RegistryAPIClient``.

Three things need to be true before an MCP client can find your agents:

1. A Registry API server is running (``agentconnect serve registry``).
2. Your hub is built with ``RegistryAPIClient`` instead of the in-process
   ``AgentRegistry``, so ``hub.register_agent(agent)`` sends registrations to that server.
3. The Discovery MCP server points at the same server (default
   ``http://localhost:8000``).

Steps 1 and 2 are covered in full in
:doc:`../../core/discovery/discovery_registry_remote`. This guide picks up at step 3 and
covers only the MCP server: starting it, connecting clients to it, and calling it
programmatically.

Starting the Server
---------------------

.. code-block:: bash

    agentconnect mcp start agent-discovery

This starts a stdio MCP server built by
:func:`create_agent_discovery_mcp <agentconnect.mcp.registry_mcp_server.create_agent_discovery_mcp>`.
It reads ``clients.registry.base_url`` from ``agentconnect.yaml``, checks the registry's
``/health`` endpoint on startup, and rechecks on any tool call made while that check was
failing.

Override the registry URL for a single run without touching the YAML file:

.. code-block:: bash

    agentconnect mcp start agent-discovery --registry-url http://my-registry:9000

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Flag
     - Effect
   * - ``--registry-url``
     - Registry API base URL for this run only. Falls back to
       ``clients.registry.base_url`` when omitted.

Tool defaults come from ``mcp.agent_discovery`` in ``agentconnect.yaml``:

.. code-block:: yaml

    clients:
      registry:
        base_url: "http://localhost:8000"

    mcp:
      agent_discovery:
        top_k: 5
        strictness: 0.2
        output_detail: "summary"   # minimal | summary | capabilities | full

See :doc:`../../configuration/sdk_configuration` for how this file is discovered and
merged.

Connecting a Client
---------------------

Every client launches the same command, ``poetry run agentconnect mcp start
agent-discovery``, from your project directory. Only the configuration format changes.

.. tab-set::

   .. tab-item:: Cursor

      Add to ``.cursor/mcp.json`` in your project:

      .. code-block:: json

          {
            "mcpServers": {
              "agentconnect-registry": {
                "type": "stdio",
                "command": "poetry",
                "args": ["run", "agentconnect", "mcp", "start", "agent-discovery"]
              }
            }
          }

   .. tab-item:: Claude Desktop

      Add to ``claude_desktop_config.json`` (Settings > Developer > Edit Config). Claude
      Desktop does not run inside your project, so pass ``--directory`` explicitly:

      .. code-block:: json

          {
            "mcpServers": {
              "agentconnect-registry": {
                "command": "poetry",
                "args": [
                  "--directory", "/path/to/AgentConnect",
                  "run", "agentconnect", "mcp", "start", "agent-discovery"
                ]
              }
            }
          }

      Fully quit and reopen Claude Desktop after saving; it only reads this file on
      launch.

   .. tab-item:: Claude Code

      Register it from your project directory. Everything after ``--`` is passed straight
      to the server:

      .. code-block:: bash

          claude mcp add agentconnect-registry -- poetry run agentconnect mcp start agent-discovery

      Add ``--scope user`` to make it available in every project instead of just this one.

   .. tab-item:: Codex CLI

      Add a table to ``~/.codex/config.toml`` (or a project-scoped
      ``.codex/config.toml``):

      .. code-block:: toml

          [mcp_servers.agentconnect-registry]
          command = "poetry"
          args = ["run", "agentconnect", "mcp", "start", "agent-discovery"]

      Or register it from the CLI:

      .. code-block:: bash

          codex mcp add agentconnect-registry -- poetry run agentconnect mcp start agent-discovery

   .. tab-item:: Other clients

      Any client that supports a stdio MCP server works the same way. Point its command at
      ``poetry run agentconnect mcp start agent-discovery`` (or the ``uv run`` equivalent)
      with the working directory set to your AgentConnect project.

.. admonition:: Windows note
   :class: note

   Use the full path to ``poetry.exe`` or ``uv.exe`` if your client does not inherit your
   shell's ``PATH``, and set the project directory through the client's own directory
   option rather than relying on the current working directory.

Calling the Tool
-------------------

Once connected, ask the client in plain language:

.. code-block:: text

    Find agents that can help with telegram broadcasting and automation

The client calls ``search_for_agents`` with a ``query``, and optionally ``top_k``,
``strictness``, ``output_detail``, and ``include_tags``. These are the same parameters and
detail levels documented in :doc:`../../systems/agent_toolbox`, since the MCP tool and the
``AIAgent`` built-in tool call the same registry search underneath.

Each result carries an ``agent_id``. That is the current boundary: an MCP client can
discover any agent registered to the shared registry, but acting on that ``agent_id``
today means using AgentConnect's own collaboration tools, which only reach agents in the
same hub. See the discovery-boundary note in
:doc:`../../core/discovery/discovery_registry_remote` for the current state of
cross-process messaging.

Programmatic Usage
---------------------

Build a server instance directly instead of going through the CLI:

.. code-block:: python

    from agentconnect.mcp.registry_mcp_server import create_agent_discovery_mcp

    mcp = create_agent_discovery_mcp()
    mcp.run()

Point it at a specific registry by passing a configured client:

.. code-block:: python

    from agentconnect.mcp.registry_mcp_server import create_agent_discovery_mcp
    from agentconnect.clients import RegistryAPIClient

    client = RegistryAPIClient(base_url="http://localhost:8000")
    mcp = create_agent_discovery_mcp(registry_client=client)
    mcp.run()

.. dropdown:: Call the tool from a Python MCP client (click to expand)
   :color: primary
   :icon: code

   .. code-block:: python

       import asyncio, json
       from mcp import ClientSession, StdioServerParameters
       from mcp.client.stdio import stdio_client
       from agentconnect.core.registry.search import AgentSearchOutput

       async def find_agents():
           params = StdioServerParameters(
               command="poetry",
               args=["run", "agentconnect", "mcp", "start", "agent-discovery"],
           )
           async with stdio_client(params) as (read, write):
               async with ClientSession(read, write) as session:
                   await session.initialize()
                   result = await session.call_tool(
                       "search_for_agents",
                       {"query": "data analysis and ML", "top_k": 3, "strictness": 0.4},
                   )
                   data = json.loads(result.content[0].text)
                   output = AgentSearchOutput.model_validate(data)
                   print(output.message, len(output.results))

       asyncio.run(find_agents())

For interactive debugging without writing a client, use the MCP Inspector:

.. code-block:: bash

    mcp dev agentconnect/mcp/registry_mcp_server.py

Troubleshooting
------------------

- **Red or disconnected signal in the client**: run ``agentconnect doctor``. It reports
  whether ``clients.registry.base_url`` resolves and whether the server answers
  ``/health``.
- **"Registry API server is not available"**: the Registry API server is not running, or
  ``base_url`` points at the wrong host. Confirm with ``agentconnect registry ping``.
- **Empty results**: lower ``strictness`` toward ``0.1``-``0.2``, drop ``include_tags``, or
  confirm the agents were registered to this same server with
  ``client.get_all_agents()``.
- **Client can't find the command**: some clients don't inherit your shell's ``PATH``. Use
  an absolute path to ``poetry`` or ``uv`` in the client configuration.

.. admonition:: On the horizon
   :class: note

   Discovery is the first MCP surface AgentConnect exposes. A per-hub MCP server that
   exposes collaboration itself, sending a request to an agent and checking its result,
   is planned for a future release, with authentication handled by the hub rather than
   the calling client.

See Also
----------

- :doc:`../../core/discovery/discovery_registry_remote` starts the Registry API server and
  registers agents to it.
- :doc:`../../systems/agent_toolbox` has the full parameter reference for
  ``search_for_agents`` and the rest of the collaboration toolbox.
- :doc:`../../configuration/sdk_configuration` covers ``agentconnect.yaml`` precedence and
  the full ``mcp.agent_discovery`` field list.
- `AgentConnect MCP README <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/mcp/README.md>`_
  covers server internals and adding new tools.
