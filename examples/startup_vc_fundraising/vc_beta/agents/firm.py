"""VC Beta firm. Climate and robotics."""

from __future__ import annotations

import json
import os
from pathlib import Path

from agentconnect.prebuilt import AIAgent

_MODEL = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
_THESIS = json.loads(
    (Path(__file__).resolve().parent.parent / "thesis.json").read_text(encoding="utf-8")
)


class Firm(AIAgent):
    """Reads a thesis file and returns a structured offer."""

    profile = {
        "summary": "VC Beta. Climate and robotics. Seed to Series B. Moderate speed.",
        "skills": [
            {
                "name": "vc_offer",
                "description": "Return a structured offer and one clarifying question.",
            }
        ],
        "tags": ["vc", "climate", "robotics", "seed", "series-b"],
    }

    def __init__(self, name: str = "firm"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You are VC Beta. Thesis: "
                f"{json.dumps(_THESIS)}. "
                "Return a short offer: valuation range, check size, lead or follow, "
                "conditions, and one clarifying question."
            ),
        )
