"""AgentConnect CLI.

A person is a Client of the Team. ``up`` starts the Runtime from
``agentconnect.yaml``. The other commands talk to that Runtime over
loopback HTTP as the reserved ``operator`` Membership.

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
import signal
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from agentconnect import __version__
from agentconnect.cli import doctor as doctor_cmds
from agentconnect.cli.client import RuntimeClient
from agentconnect.cli.hosting import (
    ensure_cwd_on_path,
    import_symbol,
    join_hosted_agent,
    team_from_config,
)
from agentconnect.cli.state import clear_state, read_state, write_state
from agentconnect.cli.templates import AGENTS_INIT_PY, ASSISTANT_PY
from agentconnect.config.loaders import load_team_config
from agentconnect.config.models import HostedAgentConfig, TeamConfig
from agentconnect.team.errors import TeamError

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Start a Team and talk to it as a person.",
)


def _die(message: str, code: int = 1) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


def _emit(data: Any, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return
    if isinstance(data, str):
        typer.echo(data)
        return
    typer.echo(json.dumps(data, indent=2))


def _resolve_url(
    url: Optional[str],
    *,
    file: Optional[Path] = None,
    root: Optional[Path] = None,
) -> str:
    if url:
        return url.rstrip("/")
    base = root or Path.cwd()
    state = read_state(base)
    if state and isinstance(state.get("url"), str) and state["url"]:
        return str(state["url"]).rstrip("/")
    try:
        config = load_team_config(file, start=base)
    except (FileNotFoundError, ValueError):
        return "http://127.0.0.1:9000"
    return f"http://{config.host}:{config.port}"


def _client(
    url: Optional[str],
    *,
    file: Optional[Path] = None,
    timeout: float = 35.0,
) -> RuntimeClient:
    return RuntimeClient(_resolve_url(url, file=file), timeout=timeout)


def _handle_team_error(exc: TeamError) -> None:
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
            "--force", help="Overwrite agentconnect.yaml and the starter Agent."
        ),
    ] = False,
) -> None:
    """Scaffold agentconnect.yaml and one hosted Agent."""
    root = Path.cwd()
    yaml_path = root / "agentconnect.yaml"
    if yaml_path.exists() and not force:
        _die("agentconnect.yaml already exists. Use --force to overwrite.")
    try:
        config = TeamConfig(
            team=name,
            store="memory",
            embeddings="auto",
            host="127.0.0.1",
            port=9000,
            require_join_auth=True,
            agents=[
                HostedAgentConfig(
                    class_path="agents.assistant:Assistant", name="assistant"
                )
            ],
        )
    except Exception as exc:
        _die(str(exc))
    import yaml as pyyaml

    yaml_path.write_text(
        "# Scaffold from `agentconnect init`. Secrets stay in the environment.\n"
        + pyyaml.safe_dump(
            config.model_dump(by_alias=True, exclude_none=True),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    agents_dir = root / "agents"
    agents_dir.mkdir(exist_ok=True)
    init_py = agents_dir / "__init__.py"
    assistant_py = agents_dir / "assistant.py"
    if init_py.exists() and not force:
        pass
    else:
        init_py.write_text(AGENTS_INIT_PY, encoding="utf-8")
    if assistant_py.exists() and not force:
        typer.echo(f"Wrote {yaml_path} (left existing {assistant_py})")
    else:
        assistant_py.write_text(ASSISTANT_PY, encoding="utf-8")
        typer.echo(f"Wrote {yaml_path}")
        typer.echo(f"Wrote {assistant_py}")
    typer.echo("Next: agentconnect up")


@app.command("up")
def up(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", exists=True, readable=True, help="Team file."),
    ] = None,
    detach: Annotated[
        bool, typer.Option("--detach", help="Start in the background.")
    ] = False,
) -> None:
    """Start the Team and its hosted Agents from agentconnect.yaml."""
    root = Path.cwd()
    try:
        config = load_team_config(file, start=root)
    except FileNotFoundError:
        _die("agentconnect.yaml was not found. Run 'agentconnect init'.")
    except ValueError as exc:
        _die(str(exc))
    config_path = file or (root / "agentconnect.yaml")
    if detach:
        _spawn_detached(config_path, root)
        return
    try:
        asyncio.run(_run_up(config, config_path, root))
    except KeyboardInterrupt:
        raise typer.Exit(code=0)


async def _run_up(config: TeamConfig, config_path: Path, root: Path) -> None:
    ensure_cwd_on_path(root)
    team = team_from_config(config)
    await team.start()
    agents: list[Any] = []
    try:
        url = await team.serve(host=config.host, port=config.port)
        for spec in config.agents:
            cls = import_symbol(spec.class_path)
            agent = cls(name=spec.name)
            await join_hosted_agent(team, agent)
            agents.append(agent)
        write_state(
            root,
            pid=os.getpid(),
            url=url,
            team=config.team,
            config_file=str(config_path),
        )
        typer.echo(f"team {config.team} at {url}")
        typer.echo(f"mcp  {url}/mcp")
        while True:
            await asyncio.sleep(1)
    finally:
        for agent in agents:
            leave = getattr(agent, "leave", None)
            if leave is not None:
                try:
                    await leave()
                except Exception:
                    pass
        await team.stop()
        clear_state(root)


def _spawn_detached(config_path: Path, root: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "agentconnect.cli",
        "up",
        "--file",
        str(config_path.resolve()),
    ]
    kwargs: dict[str, Any] = {"cwd": str(root)}
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
def down() -> None:
    """Stop the Team started by ``up`` in this directory."""
    root = Path.cwd()
    state = read_state(root)
    if state is None or not isinstance(state.get("pid"), int):
        _die("no running Team in this directory")
    pid = int(state["pid"])
    if pid == os.getpid():
        _die("refusing to stop the current process")
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            _die(f"could not stop pid {pid}: {exc}")
    clear_state(root)
    typer.echo("stopped")


@app.command("status")
def status(
    url: Annotated[Optional[str], typer.Option("--url", help="Runtime origin.")] = None,
    file: Annotated[
        Optional[Path], typer.Option("--file", help="Team file used to resolve origin.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Show members, online state, Mailbox depths, and open Tickets."""
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
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Issue a join token for a network Agent."""
    try:
        with _client(url) as client:
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
) -> None:
    """Revoke a join token and drop Sessions created from it."""
    try:
        with _client(url) as client:
            client.revoke_token(token)
    except TeamError as exc:
        _handle_team_error(exc)
    typer.echo("revoked")


@app.command("find")
def find(
    query: Annotated[str, typer.Argument(help="Natural-language need.")],
    limit: Annotated[Optional[int], typer.Option("--limit", min=1, max=100)] = None,
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Search this Team's Directory."""
    try:
        with _client(url) as client:
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
        summary = (match.get("profile") or {}).get("summary") or ""
        score = match.get("score")
        score_text = f"  {score:.3f}" if isinstance(score, (int, float)) else ""
        typer.echo(f"{match['address']}{score_text}  {summary}")


@app.command("ask")
def ask(
    address: Annotated[str, typer.Argument(help="Recipient Address.")],
    question: Annotated[str, typer.Argument(help="Request content.")],
    deadline: Annotated[
        float, typer.Option("--deadline", help="Seconds until the Ticket expires.")
    ] = 30.0,
    url: Annotated[Optional[str], typer.Option("--url")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Send reply-expected work and wait for the Ticket."""
    content: Any = question
    stripped = question.strip()
    if stripped[:1] in "{[":
        try:
            content = json.loads(stripped)
        except json.JSONDecodeError:
            content = question
    try:
        with _client(url, timeout=max(35.0, deadline + 10.0)) as client:
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
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Print the timeline for one causal operation."""
    try:
        with _client(url) as client:
            result = client.get_trace(trace_id)
    except TeamError as exc:
        _handle_team_error(exc)
    if as_json:
        _emit(result, as_json=True)
        return
    typer.echo(f"trace {result['trace_id']}")
    for event in result.get("events") or []:
        _print_trace_event(event)


def _print_trace_event(event: dict[str, Any]) -> None:
    at = str(event.get("at") or "")
    stamp = at[11:19] if len(at) >= 19 else at
    kind = event.get("type")
    actor = event.get("actor") or ""
    detail = event.get("detail") or {}
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
) -> None:
    """Print new Trace events until interrupted."""
    client = RuntimeClient(_resolve_url(url))
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
) -> None:
    """Check the Team file, keys, and whether the Runtime is reachable."""
    doctor_cmds.doctor(url=url)


def main() -> None:
    """Entry point for the ``agentconnect`` console script."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
