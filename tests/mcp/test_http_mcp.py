"""Team MCP over loopback HTTP, including Session Bearer vs operator."""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.exceptions import MCPError

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Echoes reply-expected work."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn research notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def process_message(self, message: dict[str, Any], ctx) -> Any:
        if message.get("kind") == "request" and message.get("deadline"):
            return {"echo": message.get("content")}
        return None


def _body(result) -> dict[str, Any]:
    if result.structured_content:
        return dict(result.structured_content)
    if result.content:
        return json.loads(result.content[0].text)
    raise AssertionError("empty tool result")


@pytest.mark.asyncio
async def test_serve_exposes_mcp_url_and_operator_can_ask():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    try:
        origin = await team.serve()
        assert team.mcp_url == f"{origin}/mcp"
        await writer.join(origin)
        async with Client(team.mcp_url) as client:
            found = _body(
                await client.call_tool(
                    "find", {"query": "someone who can draft a summary"}
                )
            )
            recipient = next(
                match["address"]
                for match in found["matches"]
                if match["address"].startswith("writer@")
            )
            ticket = _body(
                await client.call_tool(
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "via-mcp",
                        "deadline_seconds": 30,
                        "wait_seconds": 8,
                    },
                )
            )
            assert ticket["state"] == "completed"
            assert ticket["response"]["content"] == {"echo": "via-mcp"}
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_http_bearer_runs_as_that_session_and_bad_token_is_not_operator():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Writer(name="researcher")
    try:
        origin = await team.serve()
        await writer.join(origin)
        await researcher.join(origin)
        token = researcher._session.session_token
        assert token

        async with create_mcp_http_client(
            headers={"Authorization": f"Bearer {token}"}
        ) as http:
            async with Client(
                streamable_http_client(
                    team.mcp_url, http_client=http, terminate_on_close=False
                )
            ) as client:
                found = _body(
                    await client.call_tool(
                        "find", {"query": "someone who can draft a summary"}
                    )
                )
                addresses = [match["address"] for match in found["matches"]]
                assert any(item.startswith("writer@") for item in addresses)
                assert all(not item.startswith("researcher@") for item in addresses)

        async with create_mcp_http_client(
            headers={"Authorization": "Bearer not-a-session"}
        ) as http:
            try:
                async with Client(
                    streamable_http_client(
                        team.mcp_url, http_client=http, terminate_on_close=False
                    )
                ) as client:
                    await client.call_tool(
                        "find", {"query": "someone who can draft a summary"}
                    )
                raise AssertionError("expected an MCP authentication error")
            except* MCPError:
                pass
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()
