# Agent examples

``basic_agent_usage.py`` creates an ``AIAgent`` and calls ``chat()`` with no
Team. Set ``AGENTCONNECT_MODEL`` and a provider key.

```bash
poetry install --extras aiagent
poetry run python examples/agents/basic_agent_usage.py
```

For Team work, use ``examples/communication/aiagent.py``.
