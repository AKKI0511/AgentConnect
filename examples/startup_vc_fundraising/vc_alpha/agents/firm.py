"""VC Alpha firm. AI, crypto, infra. Seed to Series A."""

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
        "summary": "VC Alpha. AI, crypto, and infra. Seed to Series A. Fast decisions.",
        "skills": [
            {
                "name": "vc_offer",
                "description": "Return a structured offer and one clarifying question.",
            }
        ],
        "tags": [
            "vc",
            "ai",
            "crypto",
            "infra",
            "seed",
            "series-a",
        ],
    }

    def __init__(self, name: str = "firm"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You are VC Alpha. Thesis: "
                f"{json.dumps(_THESIS)}. "
                "Return a short offer: valuation range, check size, lead or follow, "
                "conditions, and one clarifying question."
            ),
        )
