"""Startup, worker, shutdown, and restart checks for ship-desk."""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from agentconnect import AgentProfile, BaseAgent, Skill
from agentconnect.agent.errors import SessionError
from agentconnect.core.ticket import Ticket

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples" / "tool_experience"
sys.path.insert(0, str(EX))

import teammates as ship_teammates  # noqa: E402
from team import PortInUseError, start_desk  # noqa: E402


class Probe(BaseAgent):
    """Temporary member used only by CI to ask specialists."""

    profile = AgentProfile(
        summary="CI probe that asks ship-desk specialists.",
        skills=[
            Skill(name="probe", description="Ask ship-desk teammates during tests.")
        ],
    )


@pytest.fixture
def fast_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ship_teammates, "FORENSIC_DELAY_SECONDS", 0.4)
    monkeypatch.setattr(ship_teammates, "HEAP_DUMP_DELAY_SECONDS", 0.4)
    monkeypatch.setattr(ship_teammates, "NESTED_METRICS_DELAY_SECONDS", 0.4)
    monkeypatch.setattr(ship_teammates, "PRESS_NOTICE_DELAY_SECONDS", 0.15)
    monkeypatch.setattr(ship_teammates, "LAB_NOTE_SLOW_SECONDS", 0.35)
    monkeypatch.setattr(ship_teammates, "LAB_NOTE_FAST_SECONDS", 0.02)


async def _until_terminal(
    agent: BaseAgent, ticket: Ticket, timeout: float = 3.0
) -> Ticket:
    deadline = time.monotonic() + timeout
    while ticket.state == "open" and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
        ticket = await agent.get_result(ticket.id)
    return ticket


async def _after_press_ingest() -> None:
    await asyncio.sleep(ship_teammates.PRESS_NOTICE_DELAY_SECONDS + 0.1)


@pytest.mark.asyncio
async def test_desk_serves_mcp_and_workers_answer(fast_delays: None) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        parsed = urlparse(desk.mcp_url)
        assert parsed.scheme == "http"
        assert parsed.hostname == "127.0.0.1"
        assert parsed.port not in {None, 0}
        assert parsed.path.rstrip("/").endswith("/mcp")

        thread_id = str(uuid.uuid4())
        timeline = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Reconstruct the payments-api 2.4.1 canary timeline."},
                thread_id=thread_id,
            ),
        )
        assert timeline.state == "completed"
        assert timeline.response is not None
        assert (
            timeline.response.content["incident_id"]
            == ship_teammates.INCIDENT["incident_id"]
        )
        assert "prior_turns" not in timeline.response.content
        assert "follow_up" not in timeline.response.content

        revised = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "What incident identifier did you already report?"},
                thread_id=thread_id,
            ),
        )
        assert revised.state == "completed"
        assert revised.response is not None
        assert (
            revised.response.content["incident_id"]
            == ship_teammates.INCIDENT["incident_id"]
        )
        assert revised.response.content["source"] == "thread_history"

        cold = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "What incident identifier did you already report?"},
            ),
        )
        assert cold.state == "completed"
        assert cold.response is not None
        assert cold.response.content["incident_id"] is None
        assert cold.response.content["source"] == "no_prior_turn"

        metrics = await _until_terminal(
            probe,
            await probe.ask(
                "metrics-analyst",
                {"question": "What additional canary percent rolled after 10%?"},
            ),
        )
        assert metrics.state == "completed"
        assert metrics.response is not None
        assert (
            metrics.response.content["additional_canary_percent"]
            == ship_teammates.METRICS["additional_canary_percent"]
        )

        empty = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "List open SEV0 incidents in eu-west-3."},
            ),
        )
        assert empty.state == "completed"
        assert empty.response is not None
        assert empty.response.content["open_sev0"] == []

        declined = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Approve next week's payroll run."},
            ),
        )
        assert declined.state == "declined"

        failed = await _until_terminal(
            probe,
            await probe.ask(
                "metrics-analyst",
                {"task": "Decode this heap dump."},
            ),
        )
        assert failed.state == "failed"
        assert failed.error is not None
        assert "heap dumps" in failed.error.message

        pending = await probe.ask(
            "incident-triage",
            {"task": "Run a forensic reconstruction of INC-4821."},
            collect="wait",
        )
        assert pending.state == "open"
        forensic = pending
        deadline = time.monotonic() + 3.0
        while forensic.state == "open" and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            forensic = await probe.get_result(pending.id)
        assert forensic.state == "completed"
        assert forensic.response is not None
        assert forensic.response.content["span_id"] == "span-8f21"

        held = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Should we hold the payments-api 2.4.1 canary?"},
            ),
            timeout=6.0,
        )
        assert held.state == "completed"
        assert held.response is not None
        assert held.response.content["status"] == "ready"
        assert held.response.content["recommendation"] == "hold_canary"
        assert "waiting_on_teammates" not in held.response.content
        assert "metrics_ticket_id" not in held.response.content

        draft_before = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert draft_before.state == "completed"
        assert draft_before.response is not None
        assert "will not expand" not in draft_before.response.content["status"]

        await probe.tell("press-liaison", {"notice": "Legal wants hold language."})
        await _after_press_ingest()
        press = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert press.state == "completed"
        assert press.response is not None
        assert (
            "Legal wants hold language."
            in press.response.content["notices_incorporated"]
        )
        assert "will not expand the canary" in press.response.content["status"]
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_occupied_port_errors_clearly() -> None:
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    try:
        port = urlparse(desk.origin).port
        assert port is not None
        with pytest.raises(PortInUseError, match="already in use"):
            await start_desk(host="127.0.0.1", port=port, wait_hold_seconds=0.05)
    finally:
        await desk.stop()


@pytest.mark.asyncio
async def test_restart_resets_memory_and_serves_again() -> None:
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    port = urlparse(desk.origin).port
    assert port is not None
    probe = Probe(name="probe")
    old_id = ""
    try:
        await probe.join(desk.team)
        ticket = await probe.ask(
            "metrics-analyst",
            {"question": "What is p99 and error budget for payments-api 2.4.1?"},
        )
        old_id = ticket.id
        assert ticket.state == "completed"
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
        except OSError:
            break
    else:
        pytest.fail("listen port still open after stop")

    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        with pytest.raises(SessionError) as missing:
            await probe.get_result(old_id)
        assert missing.value.code == "not_found"
        fresh = await probe.ask(
            "metrics-analyst",
            {"question": "What is p99 and error budget for payments-api 2.4.1?"},
        )
        assert fresh.state == "completed"
        assert fresh.id != old_id
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_stop_cancels_delayed_forensics(fast_delays: None) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        pending = await probe.ask(
            "incident-triage",
            {"task": "Run a forensic reconstruction of INC-4821."},
            collect="ticket",
        )
        assert pending.state == "open"
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_specialists_decline_unsupported_and_honor_constraints(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)

        mixed = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {
                    "task": (
                        "Run a forensic reconstruction of INC-4821, then "
                        "recommend hold or ship"
                    )
                },
            ),
        )
        assert mixed.state == "declined"

        unrelated = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "List payments-api 2.4.1 changelog items."},
            ),
        )
        assert unrelated.state == "declined"

        legal = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": ("Draft a legal hold contract for payroll tax filing")},
            ),
        )
        assert legal.state == "declined"

        thread_id = str(uuid.uuid4())
        listed = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "List payments-api 2.4.1 changelog items."},
                thread_id=thread_id,
            ),
        )
        assert listed.state == "completed"
        assert listed.response is not None
        assert listed.response.content["filter"] == "all"

        high = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Only the high-risk 2.4.1 changes."},
                thread_id=thread_id,
            ),
        )
        assert high.state == "completed"
        assert high.response is not None
        assert high.response.content["filter"] == "high"
        assert len(high.response.content["changes"]) == 2

        reset = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Reset the filter and list all 2.4.1 changes."},
                thread_id=thread_id,
            ),
        )
        assert reset.state == "completed"
        assert reset.response is not None
        assert reset.response.content["filter"] == "all"
        assert len(reset.response.content["changes"]) > 2
        reset_ids = {row["id"] for row in reset.response.content["changes"]}

        nxt = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Next page of the changelog."},
                thread_id=thread_id,
            ),
        )
        assert nxt.state == "completed"
        assert nxt.response is not None
        assert nxt.response.content["filter"] == "all"
        next_ids = {row["id"] for row in nxt.response.content["changes"]}
        assert next_ids
        assert next_ids.isdisjoint(reset_ids)
        assert nxt.response.content["page"] == 2

        notes = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Give the INC-4821 postmortem notes."},
            ),
        )
        assert notes.state == "completed"
        assert notes.response is not None
        body = notes.response.content["notes"]
        assert isinstance(body, str)
        assert len(body) >= ship_teammates.POSTMORTEM_MIN_CHARS

        draft_before = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert draft_before.state == "completed"
        assert draft_before.response is not None
        assert (
            "has been rolled back to 2.4.0"
            not in draft_before.response.content["status"]
        )
        assert (
            "We are rolling the canary back"
            not in draft_before.response.content["status"]
        )

        await probe.tell(
            "press-liaison",
            {"notice": "Rollback the canary to 2.4.0."},
        )
        await _after_press_ingest()
        draft_after = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert draft_after.state == "completed"
        assert draft_after.response is not None
        assert (
            "Rollback the canary to 2.4.0."
            in draft_after.response.content["notices_incorporated"]
        )
        assert "has not been rolled back" in draft_after.response.content["status"]
        assert (
            "We are rolling the canary back"
            not in draft_after.response.content["status"]
        )

        await probe.tell(
            "press-liaison",
            {"notice": "Confirmed: the canary has been rolled back to 2.4.0."},
        )
        await _after_press_ingest()
        draft_confirmed = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert draft_confirmed.state == "completed"
        assert draft_confirmed.response is not None
        assert (
            "has been rolled back to 2.4.0"
            in draft_confirmed.response.content["status"]
        )
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


def test_team_py_stops_on_interrupt() -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            str(EX / "team.py"),
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        cwd=str(EX),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        creationflags=creationflags,
    )
    output: list[str] = []
    try:
        deadline = time.monotonic() + 25.0
        assert proc.stdout is not None
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if line:
                output.append(line)
                if "MCP URL" in line:
                    break
            elif proc.poll() is not None:
                pytest.fail("team.py exited before serving: " + "".join(output))
        else:
            pytest.fail("team.py did not print MCP URL: " + "".join(output))
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)
        try:
            code = proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("team.py did not stop after interrupt: " + "".join(output))
        assert code == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_postmortem_notes_are_a_bounded_longer_document() -> None:
    notes = ship_teammates.POSTMORTEM_NOTES
    assert len(notes) >= ship_teammates.POSTMORTEM_MIN_CHARS
    assert notes.count("INC-4821") >= 1
    assert "processor_timeout" in notes
    assert notes.count("payments-api") >= 3


def test_changelog_page_accounting_restarts_after_filter_change() -> None:
    def _page(filter_name: str, page: int, changes: list[str] | None = None) -> object:
        return SimpleNamespace(
            kind="response",
            content={
                "version": "2.4.1",
                "filter": filter_name,
                "page": page,
                "changes": changes or [],
                "has_more": False,
            },
        )

    ctx = SimpleNamespace(
        history=[
            _page("all", 1, ["PAY-881"]),
            _page("all", 2, ["PAY-918"]),
            _page("high", 1, ["PAY-881", "PAY-924"]),
            _page("all", 1, ["PAY-881"]),
        ]
    )
    assert ship_teammates._changelog_pages_sent(ctx, high=False) == 1
    ctx_high = SimpleNamespace(history=list(ctx.history)[:-1])
    assert ship_teammates._changelog_pages_sent(ctx_high, high=True) == 1
    sequential = SimpleNamespace(history=[_page("all", 1), _page("all", 2)])
    assert ship_teammates._changelog_pages_sent(sequential, high=False) == 2


def test_press_status_does_not_treat_preparation_as_execution() -> None:
    prepare = ship_teammates._press_status(
        ["Legal wants hold language. Please prepare rollback wording."]
    )
    assert "will not expand the canary" in prepare
    assert "has been rolled back to 2.4.0" not in prepare
    assert "We are rolling the canary back" not in prepare

    negated = ship_teammates._press_status(["Do not rollback."])
    assert "has not been rolled back" in negated
    assert "has been rolled back to 2.4.0" not in negated
    assert "We are rolling the canary back" not in negated

    instruction = ship_teammates._press_status(["Rollback the canary to 2.4.0."])
    assert "has not been rolled back" in instruction
    assert "We are rolling the canary back" not in instruction

    confirmed = ship_teammates._press_status(
        [
            "Legal wants hold language.",
            "Confirmed: the canary has been rolled back to 2.4.0.",
        ]
    )
    assert "has been rolled back to 2.4.0" in confirmed

    prohibition = (
        "Draft customer status. Do not claim the canary has been rolled "
        "back unless a confirmed rollback notice exists."
    )
    ask_after_prepare = ship_teammates._press_status(
        ["Prepare rollback wording only.", prohibition]
    )
    assert "has been rolled back to 2.4.0" not in ask_after_prepare
    assert "We are rolling the canary back" not in ask_after_prepare

    not_confirmed = ship_teammates._press_status(
        ["This is not a confirmed rollback. Prepare wording only."]
    )
    assert "has been rolled back to 2.4.0" not in not_confirmed

    fact_in_ask = ship_teammates._press_status(
        [
            "Prepare rollback wording only.",
            "Draft customer status. The canary has been rolled back to 2.4.0.",
        ]
    )
    assert "has been rolled back to 2.4.0" in fact_in_ask


@pytest.mark.asyncio
async def test_press_prepare_and_negated_rollback_keep_hold(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        before = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert before.state == "completed"
        assert before.response is not None
        assert "will not expand" not in before.response.content["status"]

        await probe.tell(
            "press-liaison",
            {"notice": ("Legal wants hold language. Please prepare rollback wording.")},
        )
        await _after_press_ingest()
        prepared = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert prepared.state == "completed"
        assert prepared.response is not None
        assert "will not expand the canary" in prepared.response.content["status"]
        assert (
            "has been rolled back to 2.4.0" not in prepared.response.content["status"]
        )
        assert (
            "We are rolling the canary back" not in prepared.response.content["status"]
        )

        await probe.tell("press-liaison", {"notice": "Do not rollback."})
        await _after_press_ingest()
        negated = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert negated.state == "completed"
        assert negated.response is not None
        assert "will not expand the canary" in negated.response.content["status"]
        assert "has been rolled back to 2.4.0" not in negated.response.content["status"]

        prohibition = (
            "Draft customer status for the payments-api canary. "
            "Do not claim the canary has been rolled back unless a "
            "confirmed rollback notice exists."
        )
        asked = await _until_terminal(
            probe,
            await probe.ask("press-liaison", prohibition),
        )
        assert asked.state == "completed"
        assert asked.response is not None
        assert "has been rolled back to 2.4.0" not in asked.response.content["status"]
        assert "We are rolling the canary back" not in asked.response.content["status"]
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_changelog_history_pages_with_small_limit(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        thread_id = str(uuid.uuid4())
        listed = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "List payments-api 2.4.1 changelog items."},
                thread_id=thread_id,
            ),
        )
        assert listed.state == "completed"
        for _ in range(3):
            page = await _until_terminal(
                probe,
                await probe.ask(
                    "changelog-scribe",
                    {"task": "Next page of the changelog."},
                    thread_id=thread_id,
                ),
            )
            assert page.state == "completed"
            assert page.response is not None
            assert page.response.content["filter"] == "all"
        newest = await probe.get_history(thread_id, limit=5)
        assert len(newest.messages) == 5
        assert newest.has_more is True
        assert newest.next_before
        older = await probe.get_history(thread_id, before=newest.next_before, limit=5)
        newest_ids = {message.id for message in newest.messages}
        older_ids = {message.id for message in older.messages}
        assert older.messages
        assert older_ids.isdisjoint(newest_ids)
        assert older.messages[-1].seq < newest.messages[0].seq
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


def test_changelog_page_accounting_restarts_after_same_filter_reset() -> None:
    def _req(text: str) -> object:
        return SimpleNamespace(kind="request", content=text)

    def _page(filter_name: str, page: int) -> object:
        return SimpleNamespace(
            kind="response",
            content={
                "version": "2.4.1",
                "filter": filter_name,
                "page": page,
                "changes": [],
                "has_more": True,
            },
        )

    ctx = SimpleNamespace(
        history=[
            _req("List payments-api 2.4.1 changelog items."),
            _page("all", 1),
            _req("Next page of the changelog."),
            _page("all", 2),
            _req("Reset the filter and list all 2.4.1 changes."),
            _page("all", 1),
        ]
    )
    assert ship_teammates._changelog_pages_sent(ctx, high=False) == 1


@pytest.mark.asyncio
async def test_same_filter_reset_then_next_unfiltered_page(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        thread_id = str(uuid.uuid4())
        first = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "List payments-api 2.4.1 changelog items."},
                thread_id=thread_id,
            ),
        )
        second = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Next page of the changelog."},
                thread_id=thread_id,
            ),
        )
        reset = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Reset the filter and list all 2.4.1 changes."},
                thread_id=thread_id,
            ),
        )
        nxt = await _until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Next page of the changelog."},
                thread_id=thread_id,
            ),
        )
        assert first.state == "completed"
        assert second.state == "completed"
        assert reset.state == "completed"
        assert nxt.state == "completed"
        assert first.response is not None
        assert second.response is not None
        assert reset.response is not None
        assert nxt.response is not None
        assert first.response.content["page"] == 1
        assert second.response.content["page"] == 2
        assert reset.response.content["filter"] == "all"
        assert reset.response.content["page"] == 1
        assert nxt.response.content["filter"] == "all"
        assert nxt.response.content["page"] == 2
        reset_ids = {row["id"] for row in reset.response.content["changes"]}
        next_ids = {row["id"] for row in nxt.response.content["changes"]}
        assert next_ids
        assert next_ids.isdisjoint(reset_ids)
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_mixed_metrics_ask_returns_slo_snapshot(fast_delays: None) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        mixed = await _until_terminal(
            probe,
            await probe.ask(
                "metrics-analyst",
                {
                    "question": (
                        "p99, 5xx, error budget, canary percent, and "
                        "additional canary percent"
                    )
                },
            ),
        )
        assert mixed.state == "completed"
        assert mixed.response is not None
        body = mixed.response.content
        assert body["p99_ms"] == ship_teammates.METRICS["p99_ms"]
        assert body["error_rate"] == ship_teammates.METRICS["error_rate"]
        assert (
            body["additional_canary_percent"]
            == ship_teammates.METRICS["additional_canary_percent"]
        )

        zero = await _until_terminal(
            probe,
            await probe.ask(
                "metrics-analyst",
                {"question": "What additional canary percent rolled after 10%?"},
            ),
        )
        assert zero.state == "completed"
        assert zero.response is not None
        assert zero.response.content == {
            "additional_canary_percent": (
                ship_teammates.METRICS["additional_canary_percent"]
            )
        }
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_timeline_follow_up_honors_or_refuses_window(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        thread_id = str(uuid.uuid4())
        full = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Reconstruct the payments-api 2.4.1 canary timeline."},
                thread_id=thread_id,
            ),
        )
        assert full.state == "completed"
        assert full.response is not None
        assert [row["at"] for row in full.response.content["timeline"]] == [
            "14:02",
            "14:11",
            "14:18",
            "14:22",
            "14:25",
        ]

        filtered = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Only include timeline events at or after 14:18."},
                thread_id=thread_id,
            ),
        )
        assert filtered.state == "completed"
        assert filtered.response is not None
        times = [row["at"] for row in filtered.response.content["timeline"]]
        assert times == ["14:18", "14:22", "14:25"]
        assert filtered.response.content["constraint"] == "after 14:18"

        refused = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "List timeline events from yesterday."},
                thread_id=thread_id,
            ),
        )
        assert refused.state == "completed"
        assert refused.response is not None
        assert refused.response.content["constraint"] == "unsupported"
        assert "HH:MM" in refused.response.content["reason"]
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_tell_accepted_is_not_processed_until_ingest(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        told = await probe.tell(
            "press-liaison",
            {"notice": "Legal wants hold language."},
        )
        assert told.status == "accepted"
        immediate = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert immediate.state == "completed"
        assert immediate.response is not None
        notices = immediate.response.content.get("notices_incorporated") or []
        assert "Legal wants hold language." not in notices
        assert "will not expand the canary" not in immediate.response.content["status"]
        await _after_press_ingest()
        later = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {"task": "Draft customer status for the payments-api canary."},
            ),
        )
        assert later.state == "completed"
        assert later.response is not None
        assert (
            "Legal wants hold language."
            in later.response.content["notices_incorporated"]
        )
        included = await _until_terminal(
            probe,
            await probe.ask(
                "press-liaison",
                {
                    "task": (
                        "Draft customer status. Legal wants hold language "
                        "and we will not expand."
                    )
                },
            ),
        )
        assert included.state == "completed"
        assert included.response is not None
        assert "will not expand the canary" in included.response.content["status"]
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()


@pytest.mark.asyncio
async def test_lab_notes_pair_out_of_order_replies_by_parent_id(
    fast_delays: None,
) -> None:
    del fast_delays
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    probe = Probe(name="probe")
    try:
        await probe.join(desk.team)
        tools = probe.team_tools()
        thread_id = str(uuid.uuid4())
        first = await probe.ask(
            "incident-triage",
            {"task": "Record this lab observation as a lab note."},
            thread_id=thread_id,
            collect="ticket",
        )
        second = await probe.ask(
            "incident-triage",
            {"task": "Record another lab note on the same conversation."},
            thread_id=thread_id,
            collect="ticket",
        )
        first_done = await _until_terminal(probe, first, timeout=3.0)
        second_done = await _until_terminal(probe, second, timeout=3.0)
        assert first_done.state == "completed"
        assert second_done.state == "completed"
        assert first_done.response is not None
        assert second_done.response is not None
        assert first_done.response.content == {"recorded": True}
        assert second_done.response.content == {"recorded": True}
        newest = await tools.get_history(thread_id=thread_id, limit=2)
        assert newest["has_more"] is True
        replies = [turn for turn in newest["messages"] if turn["kind"] == "response"]
        assert {turn["parent_id"] for turn in replies} <= {first.id, second.id}
        assert all(turn["content"] == {"recorded": True} for turn in replies)
        older = await tools.get_history(
            thread_id=thread_id, before=newest["next_before"], limit=2
        )
        requests = [turn for turn in older["messages"] if turn["kind"] == "request"]
        assert {turn["id"] for turn in requests} == {first.id, second.id}
        for turn in requests:
            assert "parent_id" not in turn
        other = str(uuid.uuid4())
        other_ticket = await _until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Reconstruct the payments-api 2.4.1 canary timeline."},
                thread_id=other,
            ),
        )
        assert other_ticket.state == "completed"
        other_history = await tools.get_history(thread_id=other)
        other_ids = {turn["id"] for turn in other_history["messages"]}
        assert first.id not in other_ids
        assert second.id not in other_ids
    finally:
        try:
            await probe.leave()
        except Exception:
            pass
        await desk.stop()
