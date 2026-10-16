"""Model-backed `BaseAgent` that calls LiteLLM for you.

Use `AIAgent` when you have a model id and want that model to answer
Team requests. Subclass `BaseAgent` when your harness already does.
`model` is a LiteLLM model id. Provider keys stay in the environment.
Pass your own functions as `tools`. Pass `complete` to replace LiteLLM.

Examples:
    `team` is started and `researcher` has joined it. After
    `pip install 'agentconnect[aiagent]'`:

    ```python
    from agentconnect.prebuilt import AIAgent

    writer = AIAgent(
        name="writer",
        model="gpt-4o-mini",
        instructions="Draft short release notes from the request.",
    )
    await writer.join(team)
    ticket = await researcher.ask("writer", "Draft a release note: search is faster.")
    if ticket.state == "completed":
        print(ticket.response.content)
    ```
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Optional, TypedDict

from agentconnect.agent.base import BaseAgent
from agentconnect.agent.context import Context
from agentconnect.agent.errors import SessionError
from agentconnect.agent.tools import Tool, ToolLike, _ensure_tool
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.message import MailboxMessage, Message
from agentconnect.core.profile import AgentProfile
from agentconnect.prebuilt.loop import (
    DEFAULT_MAX_ROUNDS,
    CompletionFn,
    messages_from_thread,
    run_tool_loop,
)


class CompletionOptions(TypedDict, total=False):
    """Keyword arguments forwarded to LiteLLM `acompletion`.

    Common fields: `temperature`, `max_tokens`, `top_p`.
    """

    temperature: float
    max_tokens: int
    top_p: float
    api_base: str


class AIAgent(BaseAgent):
    """`BaseAgent` that answers with a LiteLLM model and a short tool loop.

    `handle` reads `ctx.history` and can call Session tools. `chat` keeps
    a local history and does not attach those tools. Pass `complete` to
    replace LiteLLM with another callable of the same shape. `ToolLoopExhausted`
    propagates from `handle`, `chat`, and `complete`.
    """

    def __init__(
        self,
        name: str,
        *,
        model: str,
        profile: AgentProfile | Mapping[str, object] | None = None,
        identity: Optional[AgentIdentity] = None,
        instructions: str = (
            "You are a helpful teammate. Use tools when they help you do the work."
        ),
        tools: Optional[Sequence[ToolLike]] = None,
        max_tool_rounds: int = DEFAULT_MAX_ROUNDS,
        completion: Optional[CompletionOptions] = None,
        api_key: Optional[str] = None,
        complete: Optional[CompletionFn] = None,
        include_team_tools: bool = True,
        instance_id: Optional[str] = None,
        max_in_flight: int = 1,
        join_token: Optional[str] = None,
    ) -> None:
        """Create a model-backed Agent. It has not joined a Team yet.

        Args:
            name: Agent name, unique within the Team.
            model: LiteLLM model id, for example `gpt-4o-mini`.
            profile: Discovery Profile mapping or `AgentProfile`. A class
                attribute named `profile` is used when this is omitted.
            identity: Optional Agent identity. Omit to create one.
            instructions: System prompt for every model call.
            tools: Extra tools besides the Session Team tools. Each item is a
                plain annotated function or an explicit `Tool`.
            max_tool_rounds: Cap on model-tool-model cycles per turn.
            completion: Extra LiteLLM kwargs such as `temperature`.
            api_key: Optional key. LiteLLM also reads provider env vars.
            complete: Replace LiteLLM with another async callable of the
                same shape.
            include_team_tools: When True (default), Session Team tools are
                attached on Team turns. `chat()` never attaches them.
            instance_id: Stable id for this running copy.
            max_in_flight: How many Deliveries this Session handles at once.
            join_token: Token from `Team.issue_join_token`, when required.

        Raises:
            ValueError: `model` is empty or `max_tool_rounds` is below 1.
        """
        if not model or not str(model).strip():
            raise ValueError("model is required")
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        super().__init__(
            name=name,
            profile=profile,
            identity=identity,
            instance_id=instance_id,
            max_in_flight=max_in_flight,
            join_token=join_token,
        )
        self.model = str(model).strip()
        self.instructions = instructions
        self.max_tool_rounds = int(max_tool_rounds)
        self.completion: dict[str, object] = dict(completion or {})
        self.api_key = api_key
        self.include_team_tools = include_team_tools
        self.tools: list[Tool] = [_ensure_tool(item) for item in tools or ()]
        self._complete: CompletionFn = complete or _litellm_complete
        self._chats: dict[str, list[dict[str, object]]] = {}

    async def handle(self, message: MailboxMessage, ctx: Context) -> str:
        """Answer one Team delivery with the model.

        Prior Thread messages come from `ctx.history`. Session tools are
        included when `include_team_tools` is true. `ToolLoopExhausted`
        reaches the caller.
        """
        address = self.address
        user_text = _message_text(message)
        return await self.complete(
            user_text,
            history=ctx.history,
            current=message,
            include_team_tools=self.include_team_tools,
            self_address=address,
        )

    async def complete(
        self,
        text: str,
        *,
        history: Optional[Sequence[Message | Mapping[str, object]]] = None,
        current: Message | Mapping[str, object] | str | None = None,
        include_team_tools: Optional[bool] = None,
        self_address: Optional[str] = None,
    ) -> str:
        """Run one model turn. Used by `handle`, `chat`, and Telegram.

        Args:
            text: User turn when `current` is omitted.
            history: Prior Messages or chat dicts. Defaults to empty.
            current: This turn as a Message, chat dict, or string.
            include_team_tools: Override the constructor flag for this call.
            self_address: Address treated as this Agent in history.

        Returns:
            Model text after the tool loop.

        Raises:
            ToolLoopExhausted: The model was still calling tools after
                `max_tool_rounds`.

        Examples:
            ```python
            reply = await agent.complete("Summarize the notes.")
            ```
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
        kwargs: dict[str, object] = dict(self.completion)
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
        """Talk to this Agent without a Team.

        History stays on this object, under `conversation_id`, and is
        not a Team Thread. Session tools are not included.
        `ToolLoopExhausted` reaches the caller.

        Examples:
            ```python
            reply = await agent.chat("What is a Ticket?")
            follow = await agent.chat("Give an example.", conversation_id="chat")
            ```
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
        by_name: dict[str, Tool] = {}
        if include_team_tools:
            try:
                for tool in self.team_tools():
                    by_name[tool.name] = tool
            except SessionError:
                pass
        for tool in self.tools:
            by_name[tool.name] = tool
        return list(by_name.values())


def _message_text(message: object) -> str:
    if isinstance(message, str):
        return message
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    return _stringify(content)


def _stringify(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (dict, list)):
        return json.dumps(content, default=str)
    return str(content)


async def _litellm_complete(**kwargs: Any) -> object:
    try:
        import litellm
    except ImportError as exc:
        raise ImportError(
            "AIAgent requires the aiagent extra. "
            "Install with: pip install 'agentconnect[aiagent]'"
        ) from exc
    return await litellm.acompletion(**kwargs)
