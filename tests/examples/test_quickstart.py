"""Run the uv quickstart Team with the stub harness."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QUICKSTART = ROOT / "examples" / "quickstart"
sys.path.insert(0, str(QUICKSTART))

from team_demo.harness import RESEARCH_NOTES, StubHarness  # noqa: E402
from team_demo.run import run_team  # noqa: E402


class _FailingHarness:
    async def complete(
        self,
        *,
        instructions: str,
        task: str,
        notes: str,
        history: list[object],
    ) -> str:
        del instructions, task, notes, history
        raise RuntimeError("notes unavailable")


def _stub_with_delays(
    *,
    researcher: float = 0.0,
    writer: float = 0.0,
):
    def make(role: str) -> StubHarness:
        delay = researcher if role == "researcher" else writer
        return StubHarness(role, delay_seconds=delay)

    return make


@pytest.mark.asyncio
async def test_quickstart_stub_team_completes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ticket = await run_team(StubHarness, embeddings="hashed")
    output = capsys.readouterr().out
    assert ticket.state == "completed"
    assert "ticket state: completed" in output
    assert "ticket still open" not in output
    assert RESEARCH_NOTES in output
    assert "ask writer@content-squad" in output
    assert "three facts" not in output


@pytest.mark.asyncio
async def test_research_outlasts_wait_hold() -> None:
    """Researcher work continues after collect=wait returns open."""
    ticket = await run_team(
        _stub_with_delays(researcher=0.25),
        embeddings="hashed",
        wait_hold_seconds=0.05,
        deadline_seconds=2,
    )
    assert ticket.state == "completed"
    assert RESEARCH_NOTES in str(ticket.response.content)


@pytest.mark.asyncio
async def test_writing_outlasts_wait_hold_within_deadline() -> None:
    """Writer work that outlasts a wait hold still finishes inside the deadline.

    Collection follows the Ticket deadline, not a caller helper timeout.
    """
    ticket = await run_team(
        _stub_with_delays(writer=0.35),
        embeddings="hashed",
        wait_hold_seconds=0.05,
        deadline_seconds=2,
    )
    assert ticket.state == "completed"
    assert RESEARCH_NOTES in str(ticket.response.content)


@pytest.mark.asyncio
async def test_researcher_failure_fails_parent() -> None:
    def make(role: str) -> object:
        if role == "researcher":
            return _FailingHarness()
        return StubHarness(role)

    ticket = await run_team(
        make,
        embeddings="hashed",
        wait_hold_seconds=0.05,
        deadline_seconds=2,
    )
    assert ticket.state == "failed"
    assert "researcher failed" in ticket.error.message


@pytest.mark.asyncio
async def test_researcher_expiry_fails_parent() -> None:
    ticket = await run_team(
        _stub_with_delays(researcher=2.0),
        embeddings="hashed",
        wait_hold_seconds=0.05,
        deadline_seconds=0.4,
        sweep_interval_seconds=0.05,
    )
    assert ticket.state in {"failed", "expired"}
    assert ticket.state != "open"
    if ticket.state == "failed":
        text = ticket.error.message.lower()
        assert "expired" in text or "deadline" in text
