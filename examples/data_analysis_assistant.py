"""Data analysis Agent that reads a CSV with the stdlib.

poetry run python examples/data_analysis_assistant.py
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import statistics
from typing import Any

from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent, HumanAgent, Tool
from agentconnect.team import Team

SAMPLE = """region,revenue
east,12
west,18
east,9
west,21
"""


def summarize_csv(payload: str) -> dict[str, Any]:
    """Return row count and mean of the numeric column named revenue if present."""
    rows = list(csv.DictReader(io.StringIO(payload)))
    values = []
    for row in rows:
        raw = row.get("revenue")
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    summary: dict[str, Any] = {"rows": len(rows)}
    if values:
        summary["revenue_mean"] = statistics.fmean(values)
        summary["revenue_sum"] = sum(values)
    return summary


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    team = await Team("analytics").start()
    analyst = AIAgent(
        name="analyst",
        model=model,
        instructions=(
            "You analyze CSV text. Call summarize_csv with the CSV payload. "
            "Explain the numbers in two sentences."
        ),
        tools=[
            Tool(
                name="summarize_csv",
                description="Summarize CSV text. Expect a revenue column.",
                parameters={
                    "type": "object",
                    "properties": {"payload": {"type": "string"}},
                    "required": ["payload"],
                },
                handler=summarize_csv,
            )
        ],
    )
    human = HumanAgent(name="operator-human")
    await analyst.join(team)
    await human.join(team)
    try:
        print("Sample CSV is in the script as SAMPLE. Paste it or ask for a summary.")
        await human.start_interaction("analyst")
    finally:
        await human.leave()
        await analyst.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
