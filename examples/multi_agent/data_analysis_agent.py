"""Analyst ``AIAgent`` that summarizes CSV text with the stdlib."""

from __future__ import annotations

import csv
import io
import statistics
from typing import Any

from agentconnect.prebuilt import AIAgent, Tool


def summarize_csv(payload: str) -> dict[str, Any]:
    """Return row count and revenue stats when a revenue column is present."""
    rows = list(csv.DictReader(io.StringIO(payload)))
    values: list[float] = []
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


def create_data_analysis_agent(model: str, **kwargs: Any) -> AIAgent:
    """Return an analyst. Pass ``complete=`` in tests to skip a live model."""
    return AIAgent(
        name="analyst",
        model=model,
        instructions=(
            "You analyze CSV text. Call summarize_csv with the payload, then "
            "explain the numbers in two sentences."
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
        **kwargs,
    )
