"""Callable tools for the prebuilt model loop.

Pass a plain annotated function and the schema is derived from the signature
and docstring. Construct :class:`~agentconnect.agent.tools.Tool` when the
schema is dynamic.

    from agentconnect.prebuilt import AIAgent, Tool

    async def search_docs(query: str) -> str:
        \"\"\"Search internal docs.

        Args:
            query: The search text.
        \"\"\"
        return f"no hits for {query}"

    agent = AIAgent(
        name="researcher",
        model="gpt-4o-mini",
        tools=[search_docs],
    )
"""

from agentconnect.agent.tools import Tool

__all__ = ["Tool"]
