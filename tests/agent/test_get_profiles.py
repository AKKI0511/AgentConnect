"""Session-bound get_profiles: bulk lookup, duplicates, and per-item errors."""

from __future__ import annotations

from typing import Any

import pytest

from agentconnect.agent import BaseAgent, SessionError
from agentconnect.team import Team


class Writer(BaseAgent):
    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [{"name": "drafting", "description": "Turn notes into a draft."}],
    }

    async def handle(self, message, ctx) -> Any:
        return None


class Coordinator(BaseAgent):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.tools = self.team_tools()

    async def handle(self, message, ctx) -> Any:
        return None


@pytest.mark.asyncio
async def test_get_profiles_keeps_order_drops_duplicates_and_returns_item_errors():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Coordinator(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        found = await researcher.tools.get_profiles(
            addresses=["writer", "missing", "writer", "operator", "writer@other-team"]
        )
        statuses = [item["status"] for item in found["items"]]
        assert statuses == ["ok", "error", "error", "error"]
        assert found["items"][0]["address"].startswith("writer@")
        assert "profile" in found["items"][0]
        assert found["items"][1]["address"] == "missing"
        assert found["items"][1]["error"]["code"] == "not_found"
        assert found["items"][2]["error"]["code"] == "not_found"
        assert found["items"][3]["error"]["code"] == "address_outside_team"
        one = await researcher.tools.get_profiles(addresses=["writer"])
        assert one["items"][0]["status"] == "ok"
        with pytest.raises(SessionError) as exc:
            await researcher.tools.get_profiles(addresses=[])
        assert exc.value.code == "invalid_request"
        with pytest.raises(SessionError) as oversized:
            await researcher.tools.get_profiles(
                addresses=[f"peer{index}" for index in range(21)]
            )
        assert oversized.value.code == "invalid_request"
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()
