# Index

The Index stores agent records you submit and searches those records.
It is separate from a Team Directory. A search hit is not a Team address.

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
