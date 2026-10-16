"""Callable tools for the prebuilt model loop.

Pass a plain annotated function. The schema comes from the signature
and docstring. Construct `Tool` when the schema is dynamic.

Examples:
    `search_docs` is an existing async function, and `team` is started:

    ```python
    from agentconnect.prebuilt import AIAgent

    agent = AIAgent(
        name="researcher",
        model="gpt-4o-mini",
        tools=[search_docs],
    )
    await agent.join(team)
    ```
"""

from agentconnect.agent.tools import Tool

__all__ = ["Tool"]
