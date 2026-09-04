"""HTTP Session: join by URL, same handler code, reconnect after restart."""

from __future__ import annotations

import asyncio
import socket

import pytest

from agentconnect.team import Team
from tests.agent.conftest import EchoAgent


def _free_loopback_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


@pytest.mark.asyncio
async def test_join_by_url_same_as_embedded():
    team = await Team("content-squad", session_ttl_seconds=30).start()
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve()
        await writer.join(url)
        await researcher.join(url)
        result = await researcher.ask("writer", "via-http", deadline_seconds=8)
        assert result.state == "completed"
        assert result.content == {"echo": "via-http"}
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_join_retries_until_http_team_is_up():
    port = _free_loopback_port()
    url = f"http://127.0.0.1:{port}"
    writer = EchoAgent(name="writer")
    task = asyncio.create_task(writer.join(url))
    await asyncio.sleep(0.2)
    assert not task.done()
    team = await Team("content-squad", session_ttl_seconds=30).start()
    try:
        await team.serve(port=port)
        await asyncio.wait_for(task, timeout=8)
        assert writer.connected
        assert writer.address == "writer@content-squad"
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_reconnects_after_team_restart():
    port = _free_loopback_port()
    team = await Team("content-squad", session_ttl_seconds=15).start()
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    try:
        url = await team.serve(port=port)
        await writer.join(url)
        await researcher.join(url)
        first = await researcher.ask("writer", "before", deadline_seconds=8)
        assert first.state == "completed"
        await team.stop()

        team = await Team("content-squad", session_ttl_seconds=15).start()
        await team.serve(port=port)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 8

        async def _until_live(agent: EchoAgent) -> None:
            while loop.time() < deadline:
                try:
                    await agent.find("draft")
                    return
                except Exception:
                    await asyncio.sleep(0.15)
            raise AssertionError(f"{agent.name} did not reconnect")

        await asyncio.gather(_until_live(writer), _until_live(researcher))
        second = await researcher.ask("writer", "after", deadline_seconds=8)
        assert second.state == "completed"
        assert second.content == {"echo": "after"}
    finally:
        await writer.leave()
        await researcher.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_serve_rejects_non_loopback():
    team = await Team("content-squad").start()
    try:
        with pytest.raises(Exception) as exc:
            await team.serve(host="0.0.0.0", port=0)
        assert getattr(exc.value, "code", None) == "invalid_request"
    finally:
        await team.stop()
