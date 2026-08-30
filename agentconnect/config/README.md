## Team file

``agentconnect.yaml`` describes a Team the CLI starts. Embedded
``Team("name").start()`` needs no file.

Secrets stay in the environment. This file names the Team, the store,
how Profiles are embedded, which Agent classes this process hosts, and
extra MCP tools.

## Load it

```python
from agentconnect.config import TeamConfig, load_team_config

config = load_team_config()
print(config.team, config.port)
```

``load_team_config()`` looks in the current directory, then parents that
contain ``pyproject.toml``. Pass a path to load a specific file.

An unknown field is an error. Later Team features add fields when they
ship.

## Fields

- ``team``: lowercase DNS label
- ``store``: ``memory`` or a ``redis://`` / ``rediss://`` URL
- ``embeddings``: ``auto``, ``none``, ``fastembed``, ``fastembed:<model>``,
  ``litellm``, or ``litellm:<model>``
- ``host`` / ``port``: loopback address ``agentconnect up`` binds
- ``require_join_auth``: when true, every join needs a token and proof
- ``agents``: hosted classes this process constructs and joins
- ``tools``: extra MCP tools as ``module:function``

```yaml
team: content-squad
store: memory
embeddings: auto
host: 127.0.0.1
port: 9000
require_join_auth: true
agents:
  - class: agents.writer:Writer
    name: writer
```

The committed example at ``agentconnect/config/agentconnect.example.yaml``
is generated from ``TeamConfig.example()``. Changing the models without
regenerating that file fails the config tests.

## Index process

The optional Index service still uses environment variables
(``AGENTCONNECT_REGISTRY_*``). See ``agentconnect/index/README.md``.
``VectorSearchSettings`` lives in ``agentconnect.config.vector``.
