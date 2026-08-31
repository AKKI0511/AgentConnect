"""Sales specialist."""

from __future__ import annotations

import os

from agentconnect.prebuilt import AIAgent

_MODEL = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")


class Sales(AIAgent):
    """Writes a short go-to-market brief."""

    profile = {
        "summary": "Writes a sales and GTM brief for investors.",
        "skills": [
            {
                "name": "sales_brief",
                "description": "Return pipeline, ICP, and GTM notes.",
            }
        ],
        "tags": ["startup", "sales"],
    }

    def __init__(self, name: str = "sales"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You are the Sales lead. Return ICP, current pipeline, and a "
                "short GTM plan. Keep it investor-ready."
            ),
        )
