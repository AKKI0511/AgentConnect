# Quickstart

AgentConnect is a runtime for teams of independent agents. Subclass
`BaseAgent`, join a `Team`, and implement `handle`. `AIAgent` is
an optional helper on a LiteLLM tool loop.

### Prerequisites

- Python 3.11 or 3.12
- Poetry
- At least one provider API key when you use a live model

### Installation

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
poetry install --with dev --extras "aiagent telegram payments cli embeddings index"
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Edit `.env` and add a provider key. `AIAgent` takes a LiteLLM model id
(`gpt-4o-mini`, `gemini/gemini-2.0-flash`, ...). LiteLLM reads the matching
env var.

```
OPENAI_API_KEY=your_openai_api_key
# or GROQ_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, ...
AGENTCONNECT_MODEL=gpt-4o-mini
```

## Two agents on one Team

The assistant discovers a researcher through Team tools (`find`, `ask`)
and returns the reply.

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent
from agentconnect.team import Team

async def main():
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    team = await Team("content-squad").start()
    researcher = AIAgent(
        name="researcher",
        model=model,
        instructions="Answer research questions in three short bullets.",
        profile={
            "summary": "Researches a topic and returns a short summary.",
            "skills": [
                {
                    "name": "research",
                    "description": "Research a topic and summarize it.",
                }
            ],
        },
    )
    assistant = AIAgent(
        name="assistant",
        model=model,
        instructions=(
            "Find a teammate who can research, ask them, and return their reply."
        ),
    )
    await researcher.join(team)
    await assistant.join(team)
    try:
        ticket = await assistant.ask(
            "researcher",
            "Summarize RAG in three short bullets.",
        )
        print(ticket.content)
    finally:
        await assistant.leave()
        await researcher.leave()
        await team.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Join starts a Session that pulls work. There is no `run()` loop on the Agent.

A recorded model (`complete=`) is how tests avoid a live API. See
`examples/communication/aiagent.py`.

## Interactive CLI chat

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent, HumanAgent
from agentconnect.team import Team

async def main():
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human")
    assistant = AIAgent(name="assistant", model=model)
    await human.join(team)
    await assistant.join(team)
    try:
        await human.start_interaction("assistant")
    finally:
        await human.leave()
        await assistant.leave()
        await team.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Type `exit` to stop. See `examples/example_usage.py`.

### What's Next?

- Team Runtime examples in `examples/communication/`
- [User Guides](https://AKKI0511.github.io/AgentConnect/guides/)
- [API Reference](https://AKKI0511.github.io/AgentConnect/api/)
