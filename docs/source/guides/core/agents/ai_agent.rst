AIAgent
=======

.. _ai_agent:

:class:`~agentconnect.prebuilt.AIAgent` is a :class:`~agentconnect.agent.base.BaseAgent` with a LiteLLM tool loop. It is a convenience. Subclass ``BaseAgent`` when you already have a model loop.

Install the extra first::

    pip install 'agentconnect[aiagent]'

``model`` is a LiteLLM model id, for example ``gpt-4o-mini`` or ``gemini/gemini-2.0-flash``. Provider keys stay in the environment.

When to use it
--------------

Use ``AIAgent`` when you want a model string, Team tools, and optional custom tools without wiring LiteLLM yourself.

Use ``BaseAgent`` when you already have an agent loop, or when the handler should be deterministic code.

Team work
---------

Join a Team. Conversation state for a Delivery comes from ``ctx.history``. Team tools (``find``, ``ask``, ``tell``, ``get_result``, ``get_history``) attach from the Session.

.. code-block:: python

    import os
    from agentconnect.prebuilt import AIAgent
    from agentconnect.team import Team

    async def main():
        team = await Team("content-squad").start()
        agent = AIAgent(
            name="assistant",
            model=os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini"),
            instructions="You are a concise teammate.",
        )
        await agent.join(team)

chat() without a Team
---------------------

``chat()`` keeps a local history. It does not attach Team tools.

.. code-block:: python

    agent = AIAgent(name="assistant", model="gpt-4o-mini")
    reply = await agent.chat("What is a Ticket?")

Custom tools
------------

Pass :class:`~agentconnect.prebuilt.tools.Tool` values. The handler may be sync or async.

.. code-block:: python

    from agentconnect.prebuilt import AIAgent, Tool

    async def search_docs(query: str) -> str:
        return f"no hits for {query}"

    agent = AIAgent(
        name="researcher",
        model="gpt-4o-mini",
        tools=[
            Tool(
                name="search_docs",
                description="Search internal docs.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                handler=search_docs,
            )
        ],
    )

Recorded model
--------------

Tests inject ``complete=``, an async callable with the LiteLLM ``acompletion`` shape. That path does not import LiteLLM.

.. code-block:: python

    async def complete(**kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    agent = AIAgent(name="assistant", model="recorded", complete=complete)

Constructor
-----------

- ``name``: Agent name, unique within the Team
- ``model``: LiteLLM model id (required)
- ``instructions``: system prompt
- ``tools``: extra tools besides Session Team tools
- ``max_tool_rounds``: cap on model-tool-model cycles (default 8)
- ``completion``: extra LiteLLM kwargs such as ``temperature``
- ``api_key``: optional. LiteLLM also reads provider env vars
- ``complete``: replace LiteLLM (tests)
- ``include_team_tools``: attach Session Team tools on Team turns (default True)

See :mod:`agentconnect.prebuilt.ai_agent`.
