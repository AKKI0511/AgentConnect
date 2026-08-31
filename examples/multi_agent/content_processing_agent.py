"""Content processor ``AIAgent`` that turns notes into a short draft."""

from __future__ import annotations

from typing import Any

from agentconnect.prebuilt import AIAgent, Tool


def word_count(text: str) -> dict[str, int]:
    """Return word and character counts for ``text``."""
    words = [part for part in text.split() if part]
    return {"words": len(words), "chars": len(text)}


def create_content_processing_agent(model: str, **kwargs: Any) -> AIAgent:
    """Return a writer. Pass ``complete=`` in tests to skip a live model."""
    return AIAgent(
        name="writer",
        model=model,
        instructions=(
            "Turn notes into a short draft. Call word_count on the draft before "
            "you return it."
        ),
        tools=[
            Tool(
                name="word_count",
                description="Count words and characters in a string.",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                handler=word_count,
            )
        ],
        **kwargs,
    )
