"""Finance specialist. Returns numbers from a local file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentconnect.agent import BaseAgent

_DATA = Path(__file__).resolve().parent.parent / "data" / "financials.json"


class Finance(BaseAgent):
    """Reads local financials and returns them."""

    profile = {
        "summary": "Returns runway, burn, and revenue from the local financials file.",
        "skills": [
            {
                "name": "finance_brief",
                "description": "Return current financial snapshot.",
            }
        ],
        "tags": ["startup", "finance"],
    }

    def __init__(self, name: str = "finance"):
        super().__init__(name=name)

    async def handle(self, msg, ctx) -> Any:
        if msg.kind != "request":
            return None
        if _DATA.exists():
            return json.loads(_DATA.read_text(encoding="utf-8"))
        return {"runway_months": 12, "monthly_burn": 80000, "arr": 0}
