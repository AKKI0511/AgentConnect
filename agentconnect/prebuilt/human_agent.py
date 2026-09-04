"""Terminal human on a Team.

``HumanAgent`` is a :class:`~agentconnect.agent.base.BaseAgent` that prints
incoming work and reads a reply from stdin. It needs the ``cli`` extra
(``aioconsole``).

    pip install 'agentconnect[cli]'

    from agentconnect.prebuilt import HumanAgent, AIAgent
    from agentconnect.team import Team

    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human")
    assistant = AIAgent(name="assistant", model="gpt-4o-mini")
    await human.join(team)
    await assistant.join(team)
    await human.start_interaction("assistant")
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Optional

from agentconnect.agent.base import BaseAgent
from agentconnect.agent.context import Context
from agentconnect.core.identity import AgentIdentity

_EXIT = frozenset({"exit", "quit", "bye"})


class HumanAgent(BaseAgent):
    """Person on a Team. Incoming work is printed; stdin is the reply.

    human = HumanAgent(name="operator-human")
    await human.join(team)
    await human.start_interaction("assistant")
    """

    profile = {
        "summary": "A person on this Team who reads and types replies.",
        "skills": [
            {
                "name": "text_interaction",
                "description": "Read a request and type a reply.",
            }
        ],
        "tags": ["human"],
    }

    def __init__(
        self,
        name: str,
        *,
        identity: Optional[AgentIdentity] = None,
        prompt: str = "You: ",
        read_line: Optional[Callable[[str], Awaitable[str]]] = None,
        instance_id: Optional[str] = None,
        join_token: Optional[str] = None,
    ) -> None:
        """Create a human member. It has not joined a Team yet.

        Args:
            name: Agent name, unique within the Team.
            prompt: Stdin prompt shown when a reply is needed.
            read_line: Optional async ``(prompt) -> str``. Tests and non-stdin
                UIs pass this instead of using the terminal.
        """
        super().__init__(
            name=name,
            identity=identity,
            instance_id=instance_id,
            join_token=join_token,
        )
        self.prompt = prompt
        self._read_line = read_line or _ainput

    async def handle(self, message: Any, ctx: Optional[Context] = None) -> Any:
        """Print the Delivery and wait for a typed reply.

        Empty input declines a request. ``exit``, ``quit``, or ``bye`` also
        declines.
        """
        sender = getattr(message, "sender", None)
        if sender is None and isinstance(message, Mapping):
            sender = message.get("sender")
        content = getattr(message, "content", None)
        if content is None and isinstance(message, Mapping):
            content = message.get("content")
        sender = sender or "teammate"
        print(f"{sender}: {content}")
        print("-" * 40)
        try:
            typed = await self._read_line(self.prompt)
        except (EOFError, KeyboardInterrupt):
            return None
        text = typed.strip() if typed else ""
        if not text or text.lower() in _EXIT:
            return None
        return text

    async def start_interaction(self, recipient: str) -> None:
        """Read lines from stdin and ``ask`` ``recipient`` until exit.

        Join a Team first. Type ``exit`` to stop.

            await human.start_interaction("assistant")
        """
        print(f"Talking to {recipient}. Type exit, quit, or bye to stop.")
        while True:
            try:
                typed = await self._read_line(self.prompt)
            except (EOFError, KeyboardInterrupt):
                return
            text = typed.strip() if typed else ""
            if not text:
                continue
            if text.lower() in _EXIT:
                return
            ticket = await self.ask(recipient, text)
            print(f"{recipient}: {ticket.content}")
            print("-" * 40)


async def _ainput(prompt: str) -> str:
    """Read one line from stdin. Requires ``agentconnect[cli]``."""
    try:
        import aioconsole
    except ImportError as exc:
        raise ImportError(
            "HumanAgent requires the cli extra. "
            "Install with: pip install 'agentconnect[cli]'"
        ) from exc
    return await aioconsole.ainput(prompt)
