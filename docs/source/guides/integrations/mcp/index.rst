Team MCP
=======

A Team exposes ``find``, ``ask``, ``tell``, ``get_result``, and ``get_history``
over MCP. ``Team.serve()`` mounts that server at ``{origin}/mcp``. Cursor and
Claude add the URL. Python hosts that do not speak MCP use ``team_tools()``.

All pages
---------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Team MCP
      :link: discovery_mcp
      :link-type: doc

      Serve a Team, add ``team.mcp_url`` to Cursor, and call find / ask / tell.

.. toctree::
   :maxdepth: 1
   :hidden:

   discovery_mcp
