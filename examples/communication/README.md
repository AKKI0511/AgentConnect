# Communication examples

`basic_communication.py` starts one Team, joins two members, and completes a reply-expected request through Runtime operations: `send`, `lease`, `reply`, and `get_result`.

```bash
poetry install
poetry run python examples/communication/basic_communication.py
```

The Team never holds Agent objects. Members pull work with `lease`. Model-backed agents that join over a session are a later example.

A Redis-backed Team uses the same operations. Pass a Redis URL when constructing the Team:

```python
team = await Team("content-squad", store="redis://localhost:6379/0").start()
```

Open Tickets in that store still resolve after the Runtime process restarts.
