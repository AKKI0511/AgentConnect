"""Startup, MCP, worker, shutdown, and restart smoke for ship-desk."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from mcp import Client

from agentconnect import AgentProfile, BaseAgent, Skill
from agentconnect.core.ticket import Ticket
from agentconnect.agent.errors import SessionError

EX = Path(__file__).resolve().parents[2] / "experiments" / "team_tools"
if str(EX) not in sys.path:
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


async def until_terminal(
    agent: BaseAgent, ticket: Ticket, timeout: float = 3.0
) -> Ticket:
    deadline = time.monotonic() + timeout
    while ticket.state == "open" and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
        ticket = await agent.get_result(ticket.id)
    return ticket


def mcp_body(result: Any) -> dict[str, Any]:
    if result.structured_content:
        return dict(result.structured_content)
    if result.content:
        return json.loads(result.content[0].text)
    raise AssertionError("empty tool result")


@pytest.mark.asyncio
async def test_desk_mcp_lists_tools_and_finds() -> None:
    desk = await start_desk(host="127.0.0.1", port=0, wait_hold_seconds=0.05)
    try:
        async with Client(desk.mcp_url) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert names == {
                "ask",
                "find",
                "get_history",
                "get_profiles",
                "get_result",
                "tell",
            }
            found = mcp_body(
                await client.call_tool(
                    "find",
                    {"query": "someone who can reconstruct a canary timeline"},
                )
            )
            cards = found["matches"]
            assert cards
            assert "did" not in cards[0]
            assert "profile" not in cards[0]
            addresses = {card["address"].split("@", 1)[0] for card in cards}
            assert "incident-triage" in addresses
    finally:
        await desk.stop()


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

        answered = await until_terminal(
            probe,
            await probe.ask(
                "incident-triage",
                {"task": "Reconstruct the payments-api 2.4.1 canary timeline."},
            ),
        )
        assert answered.state == "completed"
        assert answered.response is not None

        declined = await until_terminal(
            probe,
            await probe.ask(
                "changelog-scribe",
                {"task": "Approve next week's payroll run."},
            ),
        )
        assert declined.state == "declined"

        failed = await until_terminal(
            probe,
            await probe.ask(
                "metrics-analyst",
                {"task": "Decode this heap dump."},
            ),
        )
        assert failed.state == "failed"
        assert failed.error is not None

        pending = await probe.ask(
            "incident-triage",
            {"task": "Run a forensic reconstruction of INC-4821."},
            collect="wait",
        )
        assert pending.state == "open"
        forensic = await until_terminal(probe, pending)
        assert forensic.state == "completed"
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
