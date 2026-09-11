"""CLI for the uv quickstart.

Deterministic (default)::

    uv run python -m team_demo

Live OpenAI Chat Completions::

    uv run python -m team_demo --live
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from team_demo.harness import OpenAIHarness, StubHarness
from team_demo.run import run_team


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AgentConnect quickstart team.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call OpenAI from handle. Requires OPENAI_API_KEY.",
    )
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if args.live:
        live = OpenAIHarness()

        def make_live(_role: str) -> OpenAIHarness:
            return live

        asyncio.run(run_team(make_live, embeddings="auto"))
        return
    asyncio.run(run_team(StubHarness, embeddings="hashed"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
