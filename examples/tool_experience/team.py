"""Start the ship-desk Team and print its MCP URL.

Run from this directory::

    uv run python team.py

Ctrl+C stops the Team. Restarting this process resets the memory store.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import socket
import sys
from dataclasses import dataclass
from typing import Any

from agentconnect import BaseAgent, Team

from teammates import TEAMMATES

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
TEAM_NAME = "ship-desk"
WAIT_HOLD_SECONDS = 2.0


class PortInUseError(OSError):
    """The configured listen port is already bound."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(
            f"Port {port} on {host} is already in use. "
            "Stop the other process, or pass --port with a free port."
        )
        self.host = host
        self.port = port


@dataclass
class Desk:
    """A running ship-desk Team and its in-process teammates."""

    team: Team
    teammates: list[BaseAgent]
    origin: str

    @property
    def mcp_url(self) -> str:
        url = self.team.mcp_url
        if not url:
            raise RuntimeError("Team is not serving")
        return url

    async def stop(self) -> None:
        await stop_desk(self.team, self.teammates)


def _is_port_in_use(exc: BaseException) -> bool:
    if getattr(exc, "winerror", None) == 10048:
        return True
    if getattr(exc, "errno", None) in {48, 98, 10048}:
        return True
    text = str(exc).lower()
    return (
        "address already in use" in text
        or "only one usage of each socket address" in text
        or "10048" in text
        or "errno 98" in text
        or "eaddrinuse" in text
    )


def _raise_if_port_busy(host: str, port: int) -> None:
    if port == 0:
        return
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.2)
    try:
        probe.connect((host, port))
    except OSError:
        return
    finally:
        probe.close()
    raise PortInUseError(host, port)


async def start_desk(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    wait_hold_seconds: float = WAIT_HOLD_SECONDS,
) -> Desk:
    """Start the Team, join specialists, and serve MCP on ``host:port``."""
    _raise_if_port_busy(host, port)
    team = await Team(
        TEAM_NAME,
        wait_hold_seconds=wait_hold_seconds,
        embeddings="none",
    ).start()
    teammates: list[BaseAgent] = []
    try:
        for cls in TEAMMATES:
            agent = cls()
            await agent.join(team)
            teammates.append(agent)
        try:
            _raise_if_port_busy(host, port)
            origin = await team.serve(host=host, port=port)
        except SystemExit as exc:
            if port != 0:
                raise PortInUseError(host, port) from exc
            raise
        except Exception as exc:
            if _is_port_in_use(exc):
                raise PortInUseError(host, port) from exc
            raise
        return Desk(team=team, teammates=teammates, origin=origin)
    except BaseException:
        await stop_desk(team, teammates)
        raise


async def stop_desk(team: Team, teammates: list[BaseAgent] | None = None) -> None:
    """Leave teammates and stop the Team."""
    for agent in reversed(teammates or []):
        try:
            await agent.leave()
        except Exception:
            pass
    await team.stop()


def _print_banner(desk: Desk) -> None:
    print(f"Team origin: {desk.origin}")
    print(f"MCP URL:     {desk.mcp_url}")
    print()
    print("Add that URL with your coding harness's native MCP support.")
    print("Loopback calls with no Authorization header act as operator.")
    print("Operator has no mailbox and no Profile.")
    print("This is not an authenticated member Session.")
    print()
    print("Ctrl+C stops the Team and resets this memory-backed run.")
    print("Leave this process in the foreground while you work.")
    sys.stdout.flush()


def _install_stop_signals(stop: asyncio.Event) -> dict[int, Any]:
    loop = asyncio.get_running_loop()

    def request_stop(*_args: object) -> None:
        loop.call_soon_threadsafe(stop.set)

    previous: dict[int, Any] = {}
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, request_stop)
        except (ValueError, OSError):
            previous.pop(sig, None)
    return previous


def _restore_stop_signals(previous: dict[int, Any]) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


async def _run(*, host: str, port: int) -> None:
    desk = await start_desk(host=host, port=port)
    stop = asyncio.Event()
    previous = _install_stop_signals(stop)
    try:
        _print_banner(desk)
        await stop.wait()
    finally:
        _restore_stop_signals(previous)
        await desk.stop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start the ship-desk Team and print its MCP URL."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(_run(host=args.host, port=args.port))
    except PortInUseError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        raise SystemExit(0) from None


if __name__ == "__main__":
    main()
