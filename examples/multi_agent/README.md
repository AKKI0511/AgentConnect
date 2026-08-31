# Multi-agent Team

One Team with a researcher, a writer, an analyst, an optional Telegram bot,
and a terminal human. Each specialist is an `AIAgent`. Team tools (`find`,
`ask`) come from the Session.

```bash
poetry install --with research --extras "aiagent telegram cli"
poetry run python examples/multi_agent/multi_agent_system.py
```

Set `AGENTCONNECT_MODEL` (a LiteLLM id) and a provider key. Optional:

- `TELEGRAM_BOT_TOKEN` adds the Telegram member
- `TAVILY_API_KEY` adds a `web_search` tool on the researcher

Factory functions take a model string:

```python
from examples.multi_agent.research_agent import create_research_agent

researcher = create_research_agent(model="gpt-4o-mini")
await researcher.join(team)
```
