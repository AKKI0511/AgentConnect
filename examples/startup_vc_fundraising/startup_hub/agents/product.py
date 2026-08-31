"""Product specialist."""

from __future__ import annotations

import os

from agentconnect.prebuilt import AIAgent

_MODEL = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")


class Product(AIAgent):
    """Writes a short product brief for investors."""

    profile = {
        "summary": "Writes a product one-pager: vision, roadmap, moat.",
        "skills": [
            {
                "name": "product_brief",
                "description": "Return an investor-ready product brief.",
            }
        ],
        "tags": ["startup", "product"],
    }

    def __init__(self, name: str = "product"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You are the Product lead. Return a concise product one-pager: "
                "vision, 3-4 roadmap milestones, and the moat. Keep it short."
            ),
        )
