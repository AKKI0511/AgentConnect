"""One Team with researcher, writer, analyst, optional Telegram, and a human.

Requires ``agentconnect[aiagent,cli]``. Telegram needs ``TELEGRAM_BOT_TOKEN``.
Research search needs ``TAVILY_API_KEY`` and ``poetry install --with research``.

    poetry run python examples/multi_agent/multi_agent_system.py
"""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Any

from dotenv import load_dotenv

from agentconnect.prebuilt import HumanAgent
from agentconnect.team import Team
from examples.multi_agent.content_processing_agent import (
    create_content_processing_agent,
)
from examples.multi_agent.data_analysis_agent import create_data_analysis_agent
from examples.multi_agent.message_logger import print_colored
from examples.multi_agent.research_agent import create_research_agent
from examples.multi_agent.telegram_agent import create_telegram_agent


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    team = await Team("ops-squad").start()
    researcher = create_research_agent(model)
    writer = create_content_processing_agent(model)
    analyst = create_data_analysis_agent(model)
    human = HumanAgent(name="operator-human")
    telegram = None
    if telegram_token:
        telegram = create_telegram_agent(model, telegram_token)
    members = [researcher, writer, analyst, human]
    if telegram is not None:
        members.append(telegram)
    for member in members:
        await member.join(team)
    telegram_task: asyncio.Task[Any] | None = None
    if telegram is not None:
        telegram_task = asyncio.create_task(telegram.run())
    print_colored("Joined ops-squad. Type to the researcher. Type exit to stop.")
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _request_stop() -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            break
    try:
        interaction = asyncio.create_task(human.start_interaction("researcher"))
        waiter = asyncio.create_task(stop.wait())
        done, pending = await asyncio.wait(
            {interaction, waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if exc is not None:
                raise exc
    finally:
        if telegram_task is not None:
            telegram_task.cancel()
            try:
                await telegram_task
            except (asyncio.CancelledError, Exception):
                pass
        for member in reversed(members):
            await member.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
