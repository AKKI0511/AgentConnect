"""Start a Team, join specialists, send work, print the Ticket."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentconnect import Team, Ticket

from team_demo.agents import Editor, Researcher, Writer
from team_demo.harness import Harness
from team_demo.tickets import show_ticket, until_terminal

MakeHarness = Callable[[str], Harness]

TASK = "Draft a short launch note for the team runtime."


async def run_team(
    make_harness: MakeHarness,
    *,
    embeddings: str = "hashed",
    wait_hold_seconds: float | None = None,
    deadline_seconds: float = 60,
    sweep_interval_seconds: float | None = None,
) -> Ticket:
    """Run the showcase. ``make_harness`` receives ``writer`` or ``researcher``.

    Sends to ``writer`` by Address. Discovery is a separate recipe.
    Deterministic mode pins hashed embeddings so this run never calls a
    provider. Live mode can pass ``embeddings="auto"``.
    """
    team_kwargs: dict[str, Any] = {"embeddings": embeddings}
    if wait_hold_seconds is not None:
        team_kwargs["wait_hold_seconds"] = wait_hold_seconds
    if sweep_interval_seconds is not None:
        team_kwargs["sweep_interval_seconds"] = sweep_interval_seconds
    team = await Team("content-squad", **team_kwargs).start()
    editor = Editor(name="editor")
    writer = Writer(name="writer", harness=make_harness("writer"))
    researcher = Researcher(
        name="researcher",
        harness=make_harness("researcher"),
    )
    await editor.join(team)
    await writer.join(team)
    await researcher.join(team)
    try:
        print("team: content-squad")
        print(
            "joined:",
            editor.address,
            writer.address,
            researcher.address,
        )
        print(f"ask {writer.address}")
        ticket = await editor.ask(
            "writer",
            TASK,
            deadline_seconds=deadline_seconds,
        )
        ticket = await until_terminal(editor, ticket)
        show_ticket(ticket)
        if ticket.state == "open":
            print(
                "this embedded Team is about to stop; in-memory work "
                "does not resume after that"
            )
        return ticket
    finally:
        await editor.leave()
        await writer.leave()
        await researcher.leave()
        await team.stop()
