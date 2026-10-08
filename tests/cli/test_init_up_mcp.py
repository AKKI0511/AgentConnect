"""init files plus the up construction path serve MCP extras to members."""

from __future__ import annotations

import asyncio
import json
import socket
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.exceptions import MCPError

from agentconnect.agent import BaseAgent
from agentconnect.cli.hosting import (
    construct_hosted_agent,
    ensure_import_path,
    join_hosted_agent,
    team_from_config,
)
from agentconnect.cli.main import _run_up
from agentconnect.config.loaders import load_selected_team
from tests.cli.test_cli import run_cli
from mcp import Client


class Guest(BaseAgent):
    """Independently joining Agent that is not listed in the Team file."""

    profile = {
        "summary": "Joins this Team from another process.",
        "skills": [
            {
                "name": "observe",
                "description": "Watch the Team without hosting in this process.",
            }
        ],
        "tags": ["guest"],
    }

    async def handle(self, message, ctx) -> Any:
        return None


def _body(result) -> Any:
    if result.structured_content is not None:
        return result.structured_content
    if result.content:
        return result.content[0].text
    raise AssertionError("empty tool result")


def _has_pong(payload: Any) -> bool:
    if payload == "pong":
        return True
    dumped = json.dumps(payload) if not isinstance(payload, str) else payload
    return "pong" in dumped


async def _call_ping(mcp_url: str, token: str) -> Any:
    async with create_mcp_http_client(
        headers={"Authorization": f"Bearer {token}"}
    ) as http:
        async with Client(
            streamable_http_client(mcp_url, http_client=http, terminate_on_close=False)
        ) as client:
            return _body(await client.call_tool("ping", {}))


@pytest.mark.asyncio
async def test_init_up_mcp_shared_tool_two_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = run_cli("init", "--name", "demo-team", cwd=tmp_path)
    assert started.returncode == 0
    toml_path = tmp_path / "agentconnect.toml"
    toml_path.write_text(
        toml_path.read_text(encoding="utf-8").replace(
            'embeddings = "auto"', 'embeddings = "none"'
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config_path, config = load_selected_team(start=tmp_path)
    assert [spec.name for spec in config.agents] == ["assistant"]
    assert "guest" not in {spec.name for spec in config.agents}
    assert config.tools == ["tools.shared:ping"]

    for name in ("agents", "agents.assistant", "tools", "tools.shared"):
        sys.modules.pop(name, None)

    ensure_import_path(config_path.parent)
    team = team_from_config(config)
    hosted = construct_hosted_agent(config.agents[0])
    guest = Guest(name="guest")
    try:
        await team.start()
        origin = await team.serve(host=config.host, port=0)
        await join_hosted_agent(team, hosted)
        issued = await team.issue_join_token(name="guest", agent_did=guest.agent_did)
        await guest.join(origin, join_token=issued["token"])

        mcp_url = team.mcp_url
        assert mcp_url == f"{origin}/mcp"

        hosted_token = hosted._session.session_token
        guest_token = guest._session.session_token
        assert hosted_token
        assert guest_token
        assert _has_pong(await _call_ping(mcp_url, hosted_token))
        assert _has_pong(await _call_ping(mcp_url, guest_token))

        async with Client(mcp_url) as operator:
            listed = {item.name for item in (await operator.list_tools()).tools}
            assert "ping" in listed
            assert {
                "find",
                "get_profiles",
                "ask",
                "tell",
                "get_result",
                "get_history",
            }.issubset(listed)
            found = _body(
                await operator.call_tool(
                    "find", {"query": "someone who can answer a short request"}
                )
            )
            assert isinstance(found, dict)
            recipient = next(
                match["address"]
                for match in found["matches"]
                if match["address"].startswith("assistant@")
            )
            ticket = _body(
                await operator.call_tool(
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "hello",
                        "deadline_seconds": 30,
                    },
                )
            )
            assert isinstance(ticket, dict)
            assert ticket["state"] == "completed"
            assert "hello" in json.dumps(ticket)

        operator_session = await team.ensure_operator_session()
        snapshot = await team.status(operator_session)
        names = {row["name"] for row in snapshot["members"]}
        assert "assistant" in names
        assert "guest" in names

        async with create_mcp_http_client(
            headers={"Authorization": "Bearer not-a-session"}
        ) as http:
            try:
                async with Client(
                    streamable_http_client(
                        mcp_url, http_client=http, terminate_on_close=False
                    )
                ) as client:
                    await client.call_tool("ping", {})
                raise AssertionError("expected extra-tool authentication failure")
            except* MCPError:
                pass
    finally:
        for agent in (guest, hosted):
            try:
                await agent.leave()
            except Exception:
                pass
        await team.stop()
        for name in ("agents", "agents.assistant", "tools", "tools.shared"):
            sys.modules.pop(name, None)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_origin(origin: str, task: asyncio.Task[None]) -> None:
    import httpx

    deadline = time.monotonic() + 20
    async with httpx.AsyncClient(timeout=0.5) as client:
        while time.monotonic() < deadline:
            if task.done():
                exc = task.exception()
                raise AssertionError(f"up exited early: {exc}")
            try:
                response = await client.get(f"{origin}/agentconnect/v1/status")
                if response.status_code == 200:
                    return
            except Exception:
                await asyncio.sleep(0.05)
    raise AssertionError(f"Team did not become reachable at {origin}")


@pytest.mark.asyncio
async def test_cli_up_serves_init_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = run_cli("init", "--name", "demo-team", cwd=tmp_path)
    assert started.returncode == 0
    port = _free_port()
    toml_path = tmp_path / "agentconnect.toml"
    text = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        text.replace('embeddings = "auto"', 'embeddings = "none"').replace(
            "port = 9000", f"port = {port}"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config_path, config = load_selected_team(start=tmp_path)
    for name in ("agents", "agents.assistant", "tools", "tools.shared"):
        sys.modules.pop(name, None)
    task = asyncio.create_task(_run_up(config, config_path))
    origin = f"http://127.0.0.1:{port}"
    try:
        await _wait_for_origin(origin, task)
        async with Client(f"{origin}/mcp") as operator:
            listed = {item.name for item in (await operator.list_tools()).tools}
            assert "ping" in listed
            assert "find" in listed
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        for name in ("agents", "agents.assistant", "tools", "tools.shared"):
            sys.modules.pop(name, None)
