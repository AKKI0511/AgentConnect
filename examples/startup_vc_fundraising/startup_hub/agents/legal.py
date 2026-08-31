"""Legal specialist."""

from __future__ import annotations

import os

from agentconnect.prebuilt import AIAgent

_MODEL = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")


class Legal(AIAgent):
    """Flags legal issues for a fundraise."""

    profile = {
        "summary": "Flags cap table, IP, and contract issues for a Seed raise.",
        "skills": [
            {
                "name": "legal_brief",
                "description": "Return legal risks and missing documents.",
            }
        ],
        "tags": ["startup", "legal"],
    }

    def __init__(self, name: str = "legal"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You are Legal. Return cap-table, IP, and contract flags for a "
                "Seed raise. List missing data-room items."
            ),
        )
