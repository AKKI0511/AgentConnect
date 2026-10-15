"""Static producer/consumer conformance, included in the framework mypy gate."""

from typing import assert_type

from agentconnect.agent.session import Session, bind_transport
from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.operations import (
    HistoryResult,
    JoinChallenge,
    JoinRequest,
    JoinResult,
    SendRequest,
    SendResult,
)
from agentconnect.core.ticket import Ticket
from agentconnect.mcp.server import create_team_mcp
from agentconnect.team import Team
from agentconnect.team.session_auth import SessionRuntime
from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import RuntimeOperations, RuntimeTransport


def team_operations(team: Team) -> RuntimeOperations:
    return team


def team_auth(team: Team) -> SessionRuntime:
    return team


def transport_conformance(
    team: Team, embedded: InProcessTransport, http: HttpRuntimeTransport
) -> tuple[RuntimeTransport, RuntimeTransport]:
    assert_type(bind_transport(team), RuntimeTransport)
    create_team_mcp(team)
    return embedded, http


async def canonical_results(
    operations: RuntimeOperations,
    session: Session,
    http: HttpRuntimeTransport,
    embedded: InProcessTransport,
    join: JoinRequest,
    send: SendRequest,
) -> None:
    assert_type(await operations.join(request=join), JoinResult)
    assert_type(await http.join(join), JoinResult)
    assert_type(await embedded.join(join), JoinResult)
    assert_type(await operations.join_challenge(), JoinChallenge)
    assert_type(await http.join_challenge(), JoinChallenge)
    assert_type(await embedded.join_challenge(), JoinChallenge)
    assert_type(await operations.send("token", send), SendResult)
    assert_type(await http.send("token", send), SendResult)
    assert_type(await embedded.send("token", send), SendResult)
    assert_type(await operations.get_result("token", "ticket"), Ticket)
    assert_type(await session.get_result("ticket"), Ticket)
    assert_type(await operations.get_history("token", "thread"), HistoryResult)
    assert_type(await session.get_history("thread"), HistoryResult)
    assert_type(await operations.find("token", "writing"), FindResult)
    assert_type(await session.find("writing"), FindResult)
    assert_type(await operations.get_profile("token", "writer"), DirectoryEntry)
    assert_type(await session.get_entry("writer"), DirectoryEntry)
