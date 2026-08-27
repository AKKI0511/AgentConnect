# Communication examples

Agents subclass ``BaseAgent``, implement ``process_message``, and call ``join``.
The Team never holds Agent objects. Each Agent pulls work through its Session.

```bash
poetry install
poetry run python examples/communication/basic_communication.py
```

`basic_communication.py` starts an embedded Team and two Agents in one process.

`http_session.py` serves the same Team over loopback HTTP. Agents join by URL,
which is the same call you use from another process:

```python
await Writer(name="writer").join("http://127.0.0.1:9000")
```

```bash
poetry run python examples/communication/http_session.py
```

A handler can return a value (reply), return nothing (decline a request, or
finish an event), raise (fail the request), or call ``ctx.ticket()`` and answer
later. ``join`` retries while the Team is coming up and reconnects if the Team
restarts.
