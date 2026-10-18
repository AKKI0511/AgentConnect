# Index

The Index stores [`DirectoryEntry`][agentconnect.core.directory.DirectoryEntry]
snapshots you submit and searches those records. It is separate from a
Team Directory. A search hit is not a Team address. Obtain an entry with
[`BaseAgent.get_entry`][agentconnect.agent.base.BaseAgent.get_entry].

```bash
uv sync --extra index
python -m agentconnect.index.service
```

The built-in server listens on loopback and reads `AGENTCONNECT_INDEX_*`.
`AGENTCONNECT_INDEX_MODEL_NAME` is `hashed` unless you set a fastembed
model id. Install `agentconnect[embeddings]` for that model. A model
that cannot load stops the process. Records disappear when the process
stops. Put your own access control in front of
[create_index_app][agentconnect.index.service.create_index_app] before
any other host can reach it.

# Index client

[IndexClient][agentconnect.index.client.IndexClient] talks to an Index
that is already running. Same-Team discovery is
[BaseAgent.find][agentconnect.agent.base.BaseAgent.find]. Obtain a
snapshot with
[BaseAgent.get_entry][agentconnect.agent.base.BaseAgent.get_entry].

For a joined `writer` and Index already running at `http://127.0.0.1:8000`:

```python
from agentconnect.index import IndexClient

async with IndexClient("http://127.0.0.1:8000") as index:
    entry = await writer.get_entry(writer.name)
    await index.put(entry)
    hits = await index.search("draft release notes")
```

`put` inserts or replaces the snapshot at its canonical qualified Address.
A cancelled or interrupted HTTP write may already have committed; call
`get` to check. Writes are not retried. `get` returns None when that
Address is absent. `delete` succeeds when the Address is already missing.
`search` returns each match with its score. Every tag on the query must
be on the Profile.

`close` closes this connection and leaves the records in place. Reads
may retry. Writes are not retried.
