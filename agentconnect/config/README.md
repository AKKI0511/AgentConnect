## Team file

``agentconnect.toml`` or ``[tool.agentconnect]`` in ``pyproject.toml``
describes a Team the CLI starts. Embedded ``Team("name").start()`` needs
no file. A standalone file uses the unprefixed tree; only
``pyproject.toml`` wraps it in ``[tool.agentconnect]``.

Secrets stay in the environment. The file names the Team, the store,
how Profiles are embedded, which Agents this process hosts, and extra
MCP tools. ``agents`` maps canonical Agent names to hosted entries.
``entrypoint`` is a ``BaseAgent`` subclass or a synchronous factory;
both receive ``name=<mapping key>`` plus optional ``kwargs``.
Independently deployed Agents join by URL and are not listed. Extra
``tools`` are published on Team MCP; connecting a harness is a separate
step.

## Load it

```python
from agentconnect.config import TeamConfig, load_team_config

config = load_team_config()
print(config.team, config.port)
```

``load_team_config()`` never merges files. An explicit path skips
discovery and does not fall back. Otherwise discovery is
nearest-directory first, from the start path toward the filesystem
root. At each directory:

1. ``agentconnect.toml``
2. ``[tool.agentconnect]`` in ``pyproject.toml``

An unknown field is an error. Later Team features add fields when they
ship. Malformed TOML fails instead of falling back to another file.

Relative ``module:Name`` imports used by ``agentconnect up`` resolve from
the directory that contains the chosen file.

## Fields

- ``team``: lowercase DNS label
- ``store``: ``memory`` or a ``redis://`` / ``rediss://`` URL
- ``embeddings``: ``auto``, ``none``, ``hashed``, ``fastembed``,
  ``fastembed:<model>``, ``openai``, ``openai:<model>``, ``litellm``, or
  ``litellm:<model>``. ``auto`` uses local ONNX when installed, otherwise
  hashed n-grams. Ambient API keys do not select hosted embeddings.
  ``openai`` needs ``agentconnect[openai]`` (tiktoken). ``litellm`` needs
  ``agentconnect[aiagent,openai]`` and only OpenAI or Azure embedding models.
- ``host`` / ``port``: loopback address ``agentconnect up`` binds
- ``require_join_auth``: when true, every join needs a token and proof
- ``agents``: mapping of canonical Agent names to hosted entries
- ``tools``: extra MCP tools as ``module:function``

```toml
team = "content-squad"

[agents.researcher]
entrypoint = "agents.researcher:Researcher"

[agents.writer]
entrypoint = "agents.writer:Writer"
kwargs.model = "provider/model"
```

## Index process

Index settings are `IndexSettings` in `agentconnect.index` and use
`AGENTCONNECT_INDEX_*`. See `agentconnect/index/README.md`.
