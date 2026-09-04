# Prebuilt Agents

Optional helpers on top of ``BaseAgent``. They are not the product. Subclass
``BaseAgent`` when you already have a model loop. Use these when you want a
model string, a terminal, or a Telegram bot without writing that loop.

```
prebuilt/
├── ai_agent.py      # AIAgent: LiteLLM tool loop
├── human_agent.py   # HumanAgent: stdin on a Team (cli extra)
├── telegram/        # TelegramAIAgent (telegram extra)
├── loop.py          # call model, run tools, repeat
└── tools.py         # Tool
```

## AIAgent

Install ``agentconnect[aiagent]``. ``model`` is a LiteLLM model id. Team tools
attach from the Session. Conversation state for Team work is ``ctx.history``.

```python
from agentconnect.prebuilt import AIAgent, Tool
from agentconnect.team import Team

async def search_docs(query: str) -> str:
    return f"no hits for {query}"

agent = AIAgent(
    name="researcher",
    model="gpt-4o-mini",
    instructions="Search docs, then answer.",
    tools=[
        Tool(
            name="search_docs",
            description="Search internal docs.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=search_docs,
        )
    ],
)
team = await Team("content-squad").start()
await agent.join(team)
```

``chat()`` talks to the Agent with no Team. History is local to
``conversation_id``. Team tools are not attached.

```python
reply = await agent.chat("What is a Ticket?")
```

Provider keys stay in the environment (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``,
``GEMINI_API_KEY``, ...). Pass ``api_key=`` only when you need to override.

## HumanAgent

Install ``agentconnect[cli]``. The Agent prints incoming work and reads stdin.

```python
from agentconnect.prebuilt import HumanAgent

human = HumanAgent(name="operator-human")
await human.join(team)
await human.start_interaction("assistant")
```

Empty input declines a request. ``exit``, ``quit``, or ``bye`` stops
``start_interaction``.

## TelegramAIAgent

Install ``agentconnect[telegram]``. Extends ``AIAgent`` with a Telegram bot.
Join a Team the same way as any Agent, then ``await agent.run()`` to poll
Telegram.

```python
from agentconnect.prebuilt import TelegramAIAgent
from agentconnect.team import Team

agent = TelegramAIAgent(
    name="telegram-bot",
    model="gpt-4o-mini",
    telegram_token="...",
)
team = await Team("content-squad").start()
await agent.join(team)
await agent.run()
```

``TELEGRAM_BOT_TOKEN`` is read when ``telegram_token`` is omitted.
