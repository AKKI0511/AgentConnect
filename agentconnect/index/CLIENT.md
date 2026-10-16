# Index client

[IndexClient][agentconnect.index.client.IndexClient] talks to an Index
that is already running. Same-Team discovery is
[BaseAgent.find][agentconnect.agent.base.BaseAgent.find].

```python
from agentconnect.core.identity import AgentIdentity
from agentconnect.index import AgentRegistration, IndexClient, IndexQuery

registration = AgentRegistration(
    agent_id="writer",
    name="writer",
    summary="Drafts release notes from findings.",
    identity=AgentIdentity.create_key_based(),
)

async with IndexClient("http://127.0.0.1:8000") as client:
    stored = await client.register(registration)
    hits = await client.search(IndexQuery(query="release notes"))
    if hits:
        print(hits[0].registration.name, hits[0].score)
    await client.unregister(stored.agent_id)
```

`register` returns the stored record. Its JSON has no private key.
A repeated id raises HTTP 409. `get_registration` returns None when
the id is absent. `update_registration` and `unregister` raise HTTP 404
for an unknown id. `search` returns each match with its score. Every
tag on the query must be on the record.

`close` closes this connection and leaves the records in place. Reads
may retry. Writes are not retried.
