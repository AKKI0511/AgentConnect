"""Startup CEO. Finds product, finance, sales, and legal teammates, then briefs."""

from __future__ import annotations

import os

from agentconnect.prebuilt import AIAgent

_MODEL = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")


class CEO(AIAgent):
    """Coordinates a fundraising brief from specialist teammates."""

    profile = {
        "summary": "Coordinates fundraising. Finds teammates and assembles an investor brief.",
        "skills": [
            {
                "name": "fundraising",
                "description": "Collect product, finance, sales, and legal input into one brief.",
            }
        ],
        "tags": ["startup", "fundraising", "ceo"],
    }

    def __init__(self, name: str = "ceo"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You are the Startup CEO. Use find to locate product, finance, sales, "
                "and legal teammates. Ask each for a short brief, then return one "
                "investor-ready summary. Ask the human when two options are close."
            ),
        )
