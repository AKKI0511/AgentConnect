# AgentConnect Examples

Team Runtime examples live in `examples/communication/`. Start there.

```bash
poetry install --extras "aiagent cli"
poetry run python examples/communication/basic_communication.py
poetry run python examples/communication/aiagent.py
```

Set `AGENTCONNECT_MODEL` (a LiteLLM id such as `gpt-4o-mini`) and a provider
key when you want a live model. `aiagent.py` uses a recorded model if that
variable is unset.

Copy `example.env` to `.env` and fill in keys.

## Team Runtime

```bash
poetry run python examples/communication/basic_communication.py
poetry run python examples/communication/tools.py
poetry run python examples/communication/mcp.py
poetry run python examples/communication/trace.py
```

Hosted Team from a file:

```bash
cd examples/communication/hosted_team
poetry run agentconnect up
```

Then in another terminal:

```bash
poetry run agentconnect find "someone who can draft a summary"
poetry run agentconnect ask writer "Draft two paragraphs about the launch."
```

## Model helpers

These need `pip install 'agentconnect[aiagent]'` (and `[cli]` for stdin).

```bash
poetry run python examples/example_usage.py
poetry run python examples/example_multi_agent.py
poetry run python examples/research_assistant.py
poetry run python examples/data_analysis_assistant.py
poetry run python examples/multi_agent/multi_agent_system.py
poetry run python examples/autonomous_workflow/run_workflow_demo.py
```

`research_assistant.py` needs `poetry install --with research` and `TAVILY_API_KEY`.

Telegram members need `TELEGRAM_BOT_TOKEN` and `agentconnect[telegram]`.

## Appointment scheduler

One Team. From `examples/mcp/appointment_scheduler`:

```bash
poetry run agentconnect up
```

Then `agentconnect ask coordinator "Find a 30 minute slot next week."`

## Fundraising

Three Teams you start separately. They do not talk across Teams.

```bash
cd examples/startup_vc_fundraising/startup_hub
poetry run agentconnect up
```
