"""Operator commands for one Team.

`up` starts the Runtime from `agentconnect.toml` or
`[tool.agentconnect]` in `pyproject.toml`, then joins the hosted
Agents. The other commands call that Runtime over loopback HTTP as the
reserved `operator` Membership.

    agentconnect init
    agentconnect up
    agentconnect find "someone who can draft a summary"
    agentconnect ask writer "Draft two paragraphs"
    agentconnect trace <trace-id>
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Annotated, NoReturn, Optional, TypedDict

import typer

from agentconnect import __version__
from agentconnect.cli import doctor as doctor_cmds
from agentconnect.agent import BaseAgent
from agentconnect.core.base import JsonValue, dump_public
from collections.abc import Mapping

from agentconnect.cli.client import RuntimeClient
from agentconnect.cli.hosting import (
    construct_hosted_agent,
    ensure_import_path,
    team_from_config,
)
from agentconnect.cli.origin import resolve_runtime_origin
from agentconnect.cli.process import (
    inspect_process,
    is_owned_team_process,
    process_created_token,
    terminate_pid,
)
from agentconnect.cli.state import (
    clear_owned_state,
    publish_state,
    read_state,
)
from agentconnect.cli.templates import (
    AGENTS_INIT_PY,
    ASSISTANT_PY,
    SHARED_PY,
    TOOLS_INIT_PY,
)
from agentconnect.config.loaders import (
    TOML_FILENAME,
    dump_team_toml,
    find_config_file,
    load_selected_team,
)
from agentconnect.config.models import HostedAgentConfig, TeamConfig
from agentconnect.team.errors import TeamError

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Start a Team and talk to it as a person.",
)


def _die(message: str, code: int = 1) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


def _concise(exc: BaseException, *, limit: int = 400) -> str:
    text = str(exc).strip() or type(exc).__name__
    text = " ".join(part.strip() for part in text.splitlines() if part.strip())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _die_exc(exc: BaseException) -> NoReturn:
    _die(_concise(exc))


def _die_startup(config_path: Path, exc: BaseException) -> NoReturn:
    if os.environ.get("AGENTCONNECT_CLI_TRACE"):
        traceback.print_exc()
    _die(f"{config_path}: {_concise(exc)}")


class _LaunchOptions(TypedDict, total=False):
    cwd: str
    creationflags: int
    start_new_session: bool


def _emit(data: object, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(dump_public(data), indent=2))
        return
    if isinstance(data, str):
        typer.echo(data)
        return
    typer.echo(json.dumps(dump_public(data), indent=2))


def _resolve_url(
    url: Optional[str],
    *,
    file: Optional[Path] = None,
    root: Optional[Path] = None,
) -> str:
    try:
        return resolve_runtime_origin(url=url, file=file, start=root)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _die_exc(exc)


def _client(
    url: Optional[str],
    *,
    file: Optional[Path] = None,
    timeout: float = 35.0,
) -> RuntimeClient:
    return RuntimeClient(_resolve_url(url, file=file), timeout=timeout)


def _handle_team_error(exc: TeamError) -> NoReturn:
    _die(f"{exc.code}: {exc.message}")


@app.command("version")
def version() -> None:
    """Print the installed AgentConnect version."""
    typer.echo(__version__)


@app.command("init")
def init(
    name: Annotated[str, typer.Option("--name", help="Team name.")] = "content-squad",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Replace existing Team files and the starter Agent.",
        ),
    ] = False,
) -> None:
    """Scaffold agentconnect.toml, one hosted Agent, and a shared MCP tool.

    Writes `agentconnect.toml`, `agents/assistant.py`, and `tools/shared.py`
    in the current directory. Existing files are left alone unless
    `--force` is set.

    Examples:
        ```bash
        agentconnect init --name content-squad
        ```
    """
    root = Path.cwd()
    try:
        existing = find_config_file(root)
    except ValueError as exc:
        if not force:
            _die_exc(exc)
        existing = None
    if existing is not None and not force:
        _die(
            f"Team configuration already exists at {existing}. "
            "Start it with 'agentconnect up', or replace starter files with "
            "'agentconnect init --force'."
        )
    try:
        config = TeamConfig(
            team=name,
            store="memory",
            embeddings="auto",
            host="127.0.0.1",
            port=9000,
            require_join_auth=True,
            tools=["tools.shared:ping"],
            agents={
                "assistant": HostedAgentConfig(
                    entrypoint="agents.assistant:create_assistant",
                )
            },
        )
    except Exception as exc:
        _die_exc(exc)
    toml_path = root / TOML_FILENAME
    toml_path.write_text(
        "# Scaffold from `agentconnect init`. Secrets stay in the environment.\n"
        "# Extra tools are published on Team MCP; connecting a harness is a\n"
        "# separate step. Independently deployed Agents join by URL/token.\n"
        + dump_team_toml(config),
        encoding="utf-8",
    )
    agents_dir = root / "agents"
    agents_dir.mkdir(exist_ok=True)
    tools_dir = root / "tools"
    tools_dir.mkdir(exist_ok=True)
    init_py = agents_dir / "__init__.py"
    assistant_py = agents_dir / "assistant.py"
    tools_init_py = tools_dir / "__init__.py"
    shared_py = tools_dir / "shared.py"
    if not init_py.exists() or force:
        init_py.write_text(AGENTS_INIT_PY, encoding="utf-8")
    if not tools_init_py.exists() or force:
        tools_init_py.write_text(TOOLS_INIT_PY, encoding="utf-8")
    if not shared_py.exists() or force:
        shared_py.write_text(SHARED_PY, encoding="utf-8")
        typer.echo(f"Wrote {shared_py}")
    if assistant_py.exists() and not force:
        typer.echo(f"Wrote {toml_path} (left existing {assistant_py})")
    else:
        assistant_py.write_text(ASSISTANT_PY, encoding="utf-8")
        typer.echo(f"Wrote {toml_path}")
        typer.echo(f"Wrote {assistant_py}")
    typer.echo("Next: agentconnect up")


@app.command("up")
def up(
    file: Annotated[
        Optional[Path],
        typer.Option(
            "--file",
            help="Team file. Overrides saved state and discovery.",
        ),
    ] = None,
    detach: Annotated[
        bool, typer.Option("--detach", help="Start in the background.")
    ] = False,
) -> None:
    """Start the Team and its hosted Agents from a Team file.

    Foreground `up` binds loopback HTTP, joins hosted Agents, and blocks
    until interrupted. `--detach` starts a background process and
    returns immediately. It does not wait until the Runtime is serving.
    Run `agentconnect status` after it binds.

    Examples:
        ```bash
        agentconnect up
        agentconnect up --detach
        ```
    """
    root = Path.cwd()
    try:
        config_path, config = load_selected_team(file, start=root)
    except FileNotFoundError:
        _die("Team file was not found. Run 'agentconnect init'.")
    except (ValueError, OSError) as exc:
        _die_exc(exc)
    typer.echo(f"using {config_path}")
    existing = read_state(config_path)
    if existing and is_owned_team_process(existing, config_path):
        _die(
            f"Team {config.team} already running at {existing.get('url')} "
            f"(pid {existing.get('pid')})"
        )
    if detach:
        _spawn_detached(config_path)
        return
    try:
        asyncio.run(_run_up(config, config_path))
    except KeyboardInterrupt:
        raise typer.Exit(code=0)
    except (SystemExit, typer.Exit):
        raise
    except Exception as exc:
        _die_startup(config_path, exc)


async def _run_up(config: TeamConfig, config_path: Path) -> None:
    try:
        ensure_import_path(config_path.parent)
        team = team_from_config(config)
        agents = [
            construct_hosted_agent(name, spec) for name, spec in config.agents.items()
        ]
    except (KeyboardInterrupt, SystemExit, typer.Exit):
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _die_startup(config_path, exc)
    joined: list[BaseAgent] = []
    pid = os.getpid()
    published: Optional[str] = None
    try:
        await team.start()
        try:
            url = await team.serve(host=config.host, port=config.port)
            for agent in agents:
                await agent.join(team)
                joined.append(agent)
        except KeyboardInterrupt:
            raise
        except SystemExit as exc:
            if exc.code in {0, None}:
                raise
            _die_startup(config_path, RuntimeError(f"HTTP serving failed ({exc.code})"))
        except typer.Exit:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _die_startup(config_path, exc)
        created = process_created_token(pid)
        if not created:
            _die_startup(config_path, RuntimeError("could not read process identity"))
        try:
            publish_state(
                config_path,
                pid=pid,
                url=url,
                team=config.team,
                created=created,
            )
        except RuntimeError as exc:
            _die_startup(config_path, exc)
        published = created
        typer.echo(f"team {config.team} at {url}")
        typer.echo(f"mcp  {url}/mcp")
        while True:
            await asyncio.sleep(1)
    finally:
        for agent in joined:
            leave = getattr(agent, "leave", None)
            if leave is not None:
                try:
                    await leave()
                except Exception:
                    pass
        await team.stop()
        if published is not None:
            clear_owned_state(config_path, pid=pid, created=published)


def _spawn_detached(config_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "agentconnect.cli",
        "up",
        "--file",
        str(config_path.resolve()),
    ]
    kwargs: _LaunchOptions = {"cwd": str(config_path.parent)}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)
    typer.echo("starting Team in the background")
    typer.echo("run agentconnect status after it binds")


@app.command("down")
def down(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
) -> None:
    """Stop the process this CLI started for the selected Team file.

    A Runtime you started in Python keeps running. If this CLI cannot
    confirm that it owns the process, it leaves the process and the
    saved record alone.

    Examples:
        ```bash
        agentconnect down
        ```
    """
    root = Path.cwd()
    try:
        config_path, _config = load_selected_team(file, start=root)
    except FileNotFoundError:
        _die("no running Team in this directory")
    except (ValueError, OSError) as exc:
        _die_exc(exc)
    state = read_state(config_path)
    if state is None or not isinstance(state.get("pid"), int):
        _die(f"no running Team for {config_path}")
    pid = state["pid"]
    assert isinstance(pid, int)
    if pid == os.getpid():
        _die("refusing to stop the current process")
    recorded = state.get("created")
    recorded_token = recorded if isinstance(recorded, str) and recorded else None
    status, _live = inspect_process(pid)
    if status == "dead":
        clear_owned_state(config_path, pid=pid, created=recorded_token)
        typer.echo("stopped")
        return
    if not is_owned_team_process(state, config_path):
        if status == "unknown" or recorded_token is None:
            _die("cannot verify process identity; not killed")
        _die(f"pid {pid} is not the Team started from {config_path}; not killed")
    if recorded_token is None:
        _die("cannot verify process identity; not killed")
    try:
        terminate_pid(pid, recorded_token)
    except Exception as exc:
        _die_exc(exc)
    if inspect_process(pid)[0] != "dead":
        _die(f"pid {pid} is still running")
    clear_owned_state(config_path, pid=pid, created=recorded_token)
    typer.echo("stopped")


@app.command("status")
def status(
    url: Annotated[
        Optional[str],
        typer.Option(
            "--url",
            help="Runtime origin. Overrides --file, saved state, and discovery.",
        ),
    ] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Show members, online state, Mailbox depths, and open Tickets.

    Talks to the running Runtime as the reserved `operator` Membership.
    `--url` overrides `--file`, saved state, and discovery.

    Examples:
        ```bash
        agentconnect status
        agentconnect status --json
        ```
    """
    try:
        with _client(url, file=file) as client:
            snapshot = client.status()
    except TeamError as exc:
        _handle_team_error(exc)
    if as_json:
        _emit(snapshot, as_json=True)
        return
    typer.echo(
        f"{snapshot['team_name']}  persistence={snapshot['persistence']}  "
        f"open_tickets={snapshot['open_tickets']}"
    )
    origin = snapshot.get("origin")
    if origin:
        typer.echo(f"origin {origin}")
    for member in snapshot.get("members") or []:
        flag = "online" if member.get("online") else "offline"
        kind = member.get("kind") or "agent"
        if kind == "principal":
            typer.echo(f"  {member['address']:28} {flag:7}  principal")
            continue
        typer.echo(
            f"  {member['address']:28} {flag:7}  "
            f"mailbox={member['mailbox_depth']}  tickets={member['open_tickets']}"
        )


token_app = typer.Typer(no_args_is_help=True, help="Issue and revoke join tokens.")
app.add_typer(token_app, name="token")


@token_app.command("issue")
def token_issue(
    name: Annotated[
        Optional[str], typer.Option("--name", help="Bind the token to this Agent name.")
    ] = None,
    did: Annotated[
        Optional[str], typer.Option("--did", help="Bind the token to this Agent DID.")
    ] = None,
    ttl: Annotated[
        Optional[float], typer.Option("--ttl", help="Lifetime in seconds.")
    ] = None,
    single_use: Annotated[
        bool, typer.Option("--single-use", help="Consume the token on the first join.")
    ] = False,
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Issue a join token for a network Agent.

    `--did` binds the token to that identity. `--name` restricts the
    requested name. Omit both for an invite that any proving Agent can
    consume. Prints the token secret, then `expires_at`.

    Examples:
        ```bash
        agentconnect token issue --name writer
        ```
    """
    try:
        with _client(url, file=file) as client:
            issued = client.issue_token(
                name=name, agent_did=did, ttl_seconds=ttl, single_use=single_use
            )
    except TeamError as exc:
        _handle_team_error(exc)
    if as_json:
        _emit(issued, as_json=True)
        return
    typer.echo(issued["token"])
    typer.echo(f"expires_at {issued['expires_at']}")


@token_app.command("revoke")
def token_revoke(
    token: Annotated[str, typer.Argument(help="Token secret to revoke.")],
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
) -> None:
    """Revoke a join token and drop Sessions created from it.

    A later join with this token fails. Waiting sends from those
    Sessions return unauthorized.

    Examples:
        ```bash
        agentconnect token revoke TOKEN
        ```
    """
    try:
        with _client(url, file=file) as client:
            client.revoke_token(token)
    except TeamError as exc:
        _handle_team_error(exc)
    typer.echo("revoked")


@app.command("find")
def find(
    query: Annotated[str, typer.Argument(help="Natural-language need.")],
    limit: Annotated[Optional[int], typer.Option("--limit", min=1, max=100)] = None,
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Search this Team's Directory.

    Prints ranked Addresses and summaries. The operator is excluded from
    results. Omit `--limit` for every other member, at most 100.

    Examples:
        ```bash
        agentconnect find "someone who can draft a summary"
        ```
    """
    try:
        with _client(url, file=file) as client:
            result = client.find(query, limit=limit)
    except TeamError as exc:
        _handle_team_error(exc)
    if as_json:
        _emit(result, as_json=True)
        return
    matches = result.get("matches") or []
    if not matches:
        typer.echo("no matches")
        return
    for match in matches:
        summary = match.get("summary") or ""
        typer.echo(f"{match['address']}  {summary}")


@app.command("ask")
def ask(
    address: Annotated[str, typer.Argument(help="Recipient Address.")],
    question: Annotated[str, typer.Argument(help="Request content.")],
    deadline: Annotated[
        Optional[float],
        typer.Option(
            "--deadline",
            help="Seconds until the Ticket expires. Omit to use the Runtime work lifetime.",
        ),
    ] = None,
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Send reply-expected work and wait for the Ticket.

    The wait can end with an open Ticket. This command does not send the
    request again to collect a later reply.

    Content that looks like JSON is parsed as JSON. `--deadline` is
    seconds until the Ticket expires; omit it to use the Runtime work
    lifetime. Prints the trace id, Ticket state, and any response then
    available.

    Examples:
        ```bash
        agentconnect ask writer "Draft two paragraphs"
        ```
    """
    content: JsonValue = question
    stripped = question.strip()
    if stripped[:1] in "{[":
        try:
            content = json.loads(stripped)
        except json.JSONDecodeError:
            content = question
    try:
        with _client(
            url, file=file, timeout=max(35.0, (deadline or 0.0) + 10.0)
        ) as client:
            result = client.ask(address, content, deadline_seconds=deadline)
    except TeamError as exc:
        _handle_team_error(exc)
    message = result.get("message") or {}
    ticket = result.get("ticket") or {}
    if as_json:
        _emit(result, as_json=True)
        return
    trace_id = message.get("trace_id")
    if trace_id:
        typer.echo(f"trace {trace_id}")
    state = ticket.get("state")
    if state:
        typer.echo(f"ticket {ticket.get('id')} {state}")
    if ticket.get("response"):
        typer.echo(json.dumps(ticket["response"].get("content"), indent=2))
    elif ticket.get("error"):
        error = ticket["error"]
        typer.echo(f"{error.get('code')}: {error.get('message')}")
    elif result.get("status") == "accepted":
        typer.echo("accepted")


@app.command("trace")
def trace_cmd(
    trace_id: Annotated[str, typer.Argument(help="Trace UUID.")],
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Print the timeline for one causal operation.

    Pass a `trace_id` from `ask` or a Message. The operator sees every
    event on that trace.

    Examples:
        ```bash
        agentconnect trace TRACE_ID
        ```
    """
    try:
        with _client(url, file=file) as client:
            result = client.get_trace(trace_id)
    except TeamError as exc:
        _handle_team_error(exc)
    if as_json:
        _emit(result, as_json=True)
        return
    typer.echo(f"trace {result['trace_id']}")
    for event in result.get("events") or []:
        _print_trace_event(event)


def _print_trace_event(event: Mapping[str, object]) -> None:
    at = str(event.get("at") or "")
    stamp = at[11:19] if len(at) >= 19 else at
    kind = event.get("type")
    actor = event.get("actor") or ""
    raw_detail = event.get("detail")
    detail = raw_detail if isinstance(raw_detail, Mapping) else {}
    extra = ""
    if kind == "accepted":
        extra = f"{detail.get('sender')} -> {detail.get('recipient')}"
    elif kind == "leased":
        extra = f"attempt={detail.get('attempt')}"
    elif kind == "replied":
        extra = f"outcome={detail.get('outcome')}"
    elif kind == "ticket_closed":
        extra = f"state={detail.get('state')}"
    elif kind == "completed" and detail.get("declined"):
        extra = "declined"
    parent = event.get("parent_id")
    if parent:
        extra = f"{extra} parent={parent}".strip()
    typer.echo(f"  {stamp}  {kind:14}  {actor}  {extra}".rstrip())


@app.command("watch")
def watch(
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
) -> None:
    """Print new Trace events until interrupted.

    Streams operator Trace events from the running Runtime until Ctrl-C.

    Examples:
        ```bash
        agentconnect watch
        ```
    """
    client = RuntimeClient(_resolve_url(url, file=file))
    try:
        for item in client.watch():
            data = item.get("data")
            if isinstance(data, dict) and data.get("type"):
                _print_trace_event(data)
            else:
                typer.echo(json.dumps(item))
    except KeyboardInterrupt:
        raise typer.Exit(code=0)
    except TeamError as exc:
        _handle_team_error(exc)
    finally:
        client.close()


@app.command("doctor")
def doctor(
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Team file. Overrides saved state and discovery."),
    ] = None,
) -> None:
    """Check the Team file, selected origin, and Runtime access.

    Does not start or stop the Team. `--url` overrides `--file`, saved
    state, and discovery.

    Examples:
        ```bash
        agentconnect doctor
        ```
    """
    doctor_cmds.doctor(url=url, file=file)


def main() -> None:
    """Entry point for the ``agentconnect`` console script."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
