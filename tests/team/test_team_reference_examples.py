"""Published Team lifecycle snippets. Setup lives here, not in the docstrings."""

from __future__ import annotations

import inspect
import re
import textwrap
import uuid

import pytest
from tests.agent.conftest import EchoAgent

import agentconnect.team.directory.embedder as team_embedder
from agentconnect.team import Team
from agentconnect.team.errors import TeamError
from agentconnect.team.store.base import Store
from tests.team.conftest import join_member

_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _python_examples(obj: object) -> list[str]:
    doc = inspect.getdoc(obj)
    assert doc, f"missing docstring on {obj}"
    blocks = [textwrap.dedent(block.lstrip("\n")) for block in _FENCE.findall(doc)]
    assert blocks, f"no python example on {obj}"
    return blocks


@pytest.mark.asyncio
async def test_start_fragment_collects_work_then_closes(monkeypatch) -> None:
    import contextlib
    import io

    monkeypatch.delenv("AGENTCONNECT_JOIN_TOKEN", raising=False)
    writer = EchoAgent(name="writer")
    researcher = EchoAgent(name="researcher")
    namespace = {"writer": writer, "researcher": researcher}
    src = _python_examples(Team.start)[0]
    wrapped = "async def _example():\n" + textwrap.indent(
        src + "\nreturn team\n", "    "
    )
    exec(compile(wrapped, "<Team.start>", "exec"), namespace)
    team = None
    try:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            team = await namespace["_example"]()
        assert stdout.getvalue().strip() == str(
            {"echo": "Draft a release note from these findings: search is faster."}
        )
        assert writer.address is None
        assert researcher.address is None
        assert team.url is None
        assert not team._started
    finally:
        await writer.leave()
        await researcher.leave()
        if team is not None:
            await team.stop()


@pytest.mark.asyncio
async def test_serve_fragment_joins_by_origin(monkeypatch) -> None:
    monkeypatch.delenv("AGENTCONNECT_JOIN_TOKEN", raising=False)
    team = await Team(
        "content-squad",
        require_join_auth=True,
        session_ttl_seconds=30,
        sweep_interval_seconds=0.05,
    ).start()
    writer = EchoAgent(name="writer")
    namespace = {"team": team, "writer": writer}
    src = _python_examples(Team.serve)[0]
    wrapped = "async def _example():\n" + textwrap.indent(
        src + "\nreturn origin, issued\n", "    "
    )
    exec(compile(wrapped, "<Team.serve>", "exec"), namespace)
    try:
        origin, issued = await namespace["_example"]()
        assert origin == team.url
        assert team.mcp_url == f"{origin}/mcp"
        assert writer.address == "writer@content-squad"
        assert writer.join_token == issued.token
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_team_error_fragment_ignores_missing_and_reraises() -> None:
    team = await Team("content-squad", sweep_interval_seconds=0.05).start()
    src = _python_examples(TeamError)[0]
    wrapped = "async def _example():\n" + textwrap.indent(src, "    ")
    namespace = {"team": team, "name": "writer"}
    exec(compile(wrapped, "<TeamError>", "exec"), namespace)
    try:
        await namespace["_example"]()
        namespace["name"] = "operator"
        with pytest.raises(TeamError) as exc:
            await namespace["_example"]()
        assert exc.value.code == "forbidden"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_store_apply_fragment_rolls_back_the_duplicate_batch(
    runtime_store,
) -> None:
    store = runtime_store
    namespace = {"store": store}
    src = _python_examples(Store.apply)[0]
    wrapped = "async def _example():\n" + textwrap.indent(
        src + "\nreturn first, second, saved, members\n", "    "
    )
    exec(compile(wrapped, "<Store.apply>", "exec"), namespace)
    try:
        first, second, saved, members = await namespace["_example"]()
        assert first.ok
        assert second.ok is False
        assert second.reason == "exists"
        assert second.op_index == 1
        assert saved == {"text": "search is faster"}
        assert members == ["release"]
    finally:
        await store.delete("sample:note")
        await store.delete("sample:notes")


@pytest.mark.asyncio
async def test_send_fragment_collects_the_same_ticket(team: Team) -> None:
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    namespace = {
        "team": team,
        "session_token": researcher.session_token,
        "message_id": str(uuid.uuid4()),
    }
    src = _python_examples(Team.send)[0]
    wrapped = "async def _example():\n" + textwrap.indent(
        src + "\nreturn ticket_id\n", "    "
    )
    exec(compile(wrapped, "<Team.send>", "exec"), namespace)
    ticket_id = await namespace["_example"]()
    assert await namespace["_example"]() == ticket_id
    assert (await team.get_result(researcher.session_token, ticket_id)).state == "open"
    deliveries = await team.lease(writer.session_token)
    assert len(deliveries.deliveries) == 1
    await team.complete(writer.session_token, deliveries.deliveries[0].lease_id)
    assert (
        await team.get_result(researcher.session_token, ticket_id)
    ).state == "declined"


@pytest.mark.asyncio
async def test_embedding_callable_fragment_uses_the_existing_encoder() -> None:
    namespace = {}
    exec(
        compile(_python_examples(team_embedder)[0], "<team.embedder>", "exec"),
        namespace,
    )
    team = namespace["team"]
    await team.start()
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        found = await team.find(researcher.session_token, "draft release notes")
        assert [match.address for match in found.matches] == [writer.address]
    finally:
        await team.stop()
