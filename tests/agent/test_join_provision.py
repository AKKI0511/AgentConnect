"""In-process join tokens, and the cases that must not mint one."""

from __future__ import annotations

import asyncio

import pytest
from tests.agent.conftest import EchoAgent

from agentconnect.agent import SessionError
from agentconnect.team import Team


@pytest.mark.asyncio
async def test_in_process_auth_join_mints_a_bound_token() -> None:
    team = await Team("demo", require_join_auth=True).start()
    writer = EchoAgent(name="writer")
    caller = EchoAgent(name="caller")
    calls = 0
    issue = team.issue_join_token

    async def counting(**kwargs):
        nonlocal calls
        calls += 1
        return await issue(**kwargs)

    team.issue_join_token = counting
    try:
        await writer.join(team)
        await caller.join(team)
        assert calls == 2
        assert writer.join_token
        ticket = await caller.ask("writer", "ping")
        assert ticket.state == "completed"
        assert ticket.content == {"echo": "ping"}
        await writer.leave()
        await writer.join(team)
        assert calls == 2
        assert writer.connected
    finally:
        await writer.leave()
        await caller.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_url_join_does_not_mint_a_token() -> None:
    team = await Team("demo", require_join_auth=True).start()
    agent = EchoAgent(name="remote")
    try:
        url = await team.serve()
        with pytest.raises(SessionError) as exc:
            await agent.join(url)
        assert exc.value.code == "unauthorized"
        assert agent.join_token is None
    finally:
        await agent.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_configured_token_is_not_replaced() -> None:
    team = await Team("demo", require_join_auth=True).start()
    agent = EchoAgent(name="writer", join_token="not-a-token")
    try:
        with pytest.raises(SessionError) as exc:
            await agent.join(team)
        assert exc.value.code == "unauthorized"
        assert agent.join_token == "not-a-token"
    finally:
        await agent.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_expired_token_is_not_replaced() -> None:
    team = await Team("demo", require_join_auth=True).start()
    agent = EchoAgent(name="writer")
    try:
        issued = await team.issue_join_token(
            name=agent.name,
            agent_did=agent.agent_did,
            ttl_seconds=0.05,
        )
        await asyncio.sleep(0.1)
        with pytest.raises(SessionError) as exc:
            await agent.join(team, join_token=issued.token)
        assert exc.value.code == "unauthorized"
        assert agent.join_token == issued.token
    finally:
        await agent.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_reconnect_reuses_token_and_denial_does_not_mint() -> None:
    team = await Team("demo", require_join_auth=True).start()
    writer = EchoAgent(name="writer")
    caller = EchoAgent(name="caller")
    try:
        await writer.join(team)
        await caller.join(team)
        token = writer.join_token
        session = writer._session
        assert session is not None
        session._connected = False
        session.session_token = None
        await session._reconnect()
        assert writer.connected
        assert writer.join_token == token
        ticket = await caller.ask("writer", "again")
        assert ticket.state == "completed"
        assert ticket.content == {"echo": "again"}

        calls = 0
        issue = team.issue_join_token

        async def counting(**kwargs):
            nonlocal calls
            calls += 1
            return await issue(**kwargs)

        team.issue_join_token = counting
        await team.revoke_join_token(token)
        session._connected = False
        session.session_token = None
        await session._reconnect()
        assert calls == 0
        assert writer.join_token == token
        assert writer.connected is False
    finally:
        await writer.leave()
        await caller.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_auto_minted_token_is_not_sent_to_another_team() -> None:
    first = await Team("alpha", require_join_auth=True).start()
    second = await Team("beta", require_join_auth=False).start()
    agent = EchoAgent(name="writer")
    try:
        await agent.join(first)
        minted = agent.join_token
        assert minted
        await agent.leave()
        await agent.join(second)
        assert agent.connected
        assert agent.join_token is None
        await agent.leave()
        await agent.join(first)
        assert agent.connected
        assert agent.join_token
        assert agent.join_token != minted
    finally:
        await agent.leave()
        await first.stop()
        await second.stop()
