"""Model-backed Agent on a LiteLLM tool loop.

``AIAgent`` is a convenience on :class:`~agentconnect.agent.base.BaseAgent`.
It is not the product. Subclass ``BaseAgent`` when you already have a model
loop. Use this helper when you want a model string, Team tools, and optional
custom tools without wiring LiteLLM yourself.

Install the extra first::

    pip install 'agentconnect[aiagent]'

    from agentconnect.prebuilt import AIAgent, Tool
    from agentconnect.team import Team

    class Writer(AIAgent):
        profile = {
            "summary": "Writes short drafts from notes.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Turn notes into a two-paragraph draft.",
                }
            ],
        }

        def __init__(self, name: str = "writer"):
            super().__init__(
                name=name,
                model="gpt-4o-mini",
                instructions="Write short, plain drafts.",
            )

    team = await Team("content-squad").start()
    await Writer().join(team)

Conversation state for Team work comes from ``ctx.history``. Team tools
(``find``, ``ask``, ``tell``, ``get_result``, ``get_history``) are attached
from the Session, not as an ``AIAgent`` feature. Extra tools are yours.

``model`` is a LiteLLM model id, for example ``gpt-4o-mini`` or
``gemini/gemini-2.0-flash``. Provider keys stay in the environment.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Optional, TypedDict

from agentconnect.agent.base import BaseAgent
from agentconnect.agent.context import Context
from agentconnect.agent.errors import SessionError
from agentconnect.core.identity import AgentIdentity
from agentconnect.prebuilt.loop import (
    CompletionFn,
    DEFAULT_MAX_ROUNDS,
    messages_from_thread,
    run_tool_loop,
)
from agentconnect.prebuilt.tools import Tool, merge_tools, tools_from_team
from agentconnect.utils.payment_helper import validate_cdp_environment

logger = logging.getLogger(__name__)


class CompletionOptions(TypedDict, total=False):
    """Keyword arguments forwarded to LiteLLM ``acompletion``.

    Common fields:

    - ``temperature``
    - ``max_tokens``
    - ``top_p``
    """

    temperature: float
    max_tokens: int
    top_p: float
    api_base: str


class AIAgent(BaseAgent):
    """``BaseAgent`` that answers with a LiteLLM model and a short tool loop.

    agent = AIAgent(name="assistant", model="gpt-4o-mini")
    await agent.join(team)
    reply = await agent.chat("What does this Team do?")
    """

    def __init__(
        self,
        name: Optional[str] = None,
        *,
        model: str,
        profile: Any = None,
        identity: Optional[AgentIdentity] = None,
        instructions: str = (
            "You are a helpful teammate. Use tools when they help you do the work."
        ),
        tools: Optional[Sequence[Tool]] = None,
        max_tool_rounds: int = DEFAULT_MAX_ROUNDS,
        completion: Optional[CompletionOptions] = None,
        api_key: Optional[str] = None,
        complete: Optional[CompletionFn] = None,
        include_team_tools: bool = True,
        enable_payments: bool = False,
        wallet_data_dir: Any = None,
        agent_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        max_in_flight: int = 1,
        join_token: Optional[str] = None,
    ) -> None:
        """Create a model-backed Agent. It has not joined a Team yet.

        Args:
            name: Agent name, unique within the Team. ``agent_id`` is an alias.
            model: LiteLLM model id, for example ``gpt-4o-mini``.
            profile: Discovery Profile mapping or ``AgentProfile``. A class
                attribute named ``profile`` is used when this is omitted.
            instructions: System prompt for every model call.
            tools: Extra tools besides the Session Team tools.
            max_tool_rounds: Cap on model→tool→model cycles per turn.
            completion: Extra LiteLLM kwargs such as ``temperature``.
            api_key: Optional key. LiteLLM also reads provider env vars.
            complete: Advanced. Replace LiteLLM with another async callable
                of the same shape. Tests use this for a recorded model.
            include_team_tools: When True (default), Session Team tools are
                attached on Team turns. ``chat()`` never attaches them.
        """
        if not model or not str(model).strip():
            raise ValueError("model is required")
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        actual_enable_payments = enable_payments
        if enable_payments:
            valid, message = validate_cdp_environment()
            if not valid:
                logger.warning("payments disabled: %s", message)
                actual_enable_payments = False
        super().__init__(
            name=name,
            profile=profile,
            identity=identity,
            instance_id=instance_id,
            max_in_flight=max_in_flight,
            join_token=join_token,
            agent_id=agent_id,
            enable_payments=actual_enable_payments,
            wallet_data_dir=wallet_data_dir,
        )
        self.model = str(model).strip()
        self.instructions = instructions
        self.max_tool_rounds = int(max_tool_rounds)
        self.completion: dict[str, Any] = dict(completion or {})
        self.api_key = api_key
        self.include_team_tools = include_team_tools
        self.tools: list[Tool] = list(tools or [])
        self._complete: CompletionFn = complete or _litellm_complete
        self._chats: dict[str, list[dict[str, Any]]] = {}
        if actual_enable_payments and self.agent_kit is not None:
            self.tools = merge_tools(self.tools, _tools_from_agentkit(self.agent_kit))

    async def process_message(
        self, message: Mapping[str, Any], ctx: Optional[Context] = None
    ) -> Any:
        """Answer one Delivery with the model loop.

        Thread history comes from ``ctx.history``. Team tools attach when a
        Session exists and ``include_team_tools`` is True.
        """
        history = ctx.history if ctx is not None else []
        address = self.address
        user_text = _message_text(message)
        return await self.complete(
            user_text,
            history=history,
            current=message,
            include_team_tools=self.include_team_tools,
            self_address=address,
        )

    async def complete(
        self,
        text: str,
        *,
        history: Optional[Sequence[Mapping[str, Any]]] = None,
        current: Optional[Mapping[str, Any]] = None,
        include_team_tools: Optional[bool] = None,
        self_address: Optional[str] = None,
    ) -> str:
        """Run one model turn. Used by ``process_message``, ``chat``, and Telegram.

        reply = await agent.complete("Summarize the notes.")
        """
        attach = (
            self.include_team_tools
            if include_team_tools is None
            else include_team_tools
        )
        messages = messages_from_thread(
            history or [],
            current if current is not None else text,
            self_address=self_address or self.address,
            instructions=self.instructions,
        )
        kwargs: dict[str, Any] = dict(self.completion)
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return await run_tool_loop(
            complete=self._complete,
            model=self.model,
            messages=messages,
            tools=self._bound_tools(attach),
            max_rounds=self.max_tool_rounds,
            **kwargs,
        )

    async def chat(
        self,
        query: str,
        *,
        conversation_id: str = "chat",
    ) -> str:
        """Talk to this Agent without a Team. History is local to ``conversation_id``.

        reply = await agent.chat("What is a Ticket?")
        follow = await agent.chat("Give an example.", conversation_id="chat")
        """
        prior = self._chats.setdefault(conversation_id, [])
        reply = await self.complete(
            query,
            history=prior,
            include_team_tools=False,
        )
        prior.append({"role": "user", "content": query})
        prior.append({"role": "assistant", "content": reply})
        return reply

    def _bound_tools(self, include_team_tools: bool) -> list[Tool]:
        team: list[Tool] = []
        if include_team_tools:
            try:
                team = tools_from_team(self.team_tools())
            except SessionError:
                team = []
        return merge_tools(team, self.tools)


def _message_text(message: Mapping[str, Any] | str) -> str:
    if isinstance(message, str):
        return message
    return _stringify(message.get("content"))


def _stringify(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (dict, list)):
        return json.dumps(content, default=str)
    return str(content)


async def _litellm_complete(**kwargs: Any) -> Any:
    try:
        import litellm
    except ImportError as exc:
        raise ImportError(
            "AIAgent requires the aiagent extra. "
            "Install with: pip install 'agentconnect[aiagent]'"
        ) from exc
    return await litellm.acompletion(**kwargs)


def _tools_from_agentkit(agent_kit: Any) -> list[Tool]:
    get_actions = getattr(agent_kit, "get_actions", None)
    if get_actions is None:
        return []
    tools: list[Tool] = []
    try:
        actions = list(get_actions())
    except Exception:
        logger.warning("AgentKit get_actions failed", exc_info=True)
        return []
    for action in actions:
        name = getattr(action, "name", None)
        if not name:
            continue
        description = str(getattr(action, "description", None) or name)
        schema = getattr(action, "args_schema", None) or {
            "type": "object",
            "properties": {},
        }
        if not isinstance(schema, dict):
            dump = getattr(schema, "model_json_schema", None)
            schema = dump() if callable(dump) else {"type": "object", "properties": {}}
        invoke = getattr(action, "invoke", None) or getattr(action, "run", None)
        if invoke is None:
            continue
        tools.append(
            Tool(
                name=str(name),
                description=description,
                parameters=schema,
                handler=invoke,
            )
        )
    return tools
