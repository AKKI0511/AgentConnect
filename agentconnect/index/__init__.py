"""Optional catalog of Directory entries you submit yourself.

A Team Directory lists members of one Team. Put a
[`DirectoryEntry`][agentconnect.core.directory.DirectoryEntry] snapshot
in an Index, then search the records that process is holding. A search
hit is not a Team address. Obtain an entry with
[`BaseAgent.get_entry`][agentconnect.agent.base.BaseAgent.get_entry].

Start
[`create_index_app`][agentconnect.index.service.create_index_app] with
`python -m agentconnect.index.service`. It listens on loopback and reads
[`IndexSettings`][agentconnect.index.models.IndexSettings]. Records
disappear when the process stops. `model_name` is `hashed` unless you
set a fastembed model id. A model that cannot load stops the process.

Examples:
    For a joined `writer` and connected Index client `index`:

    ```python
    entry = await writer.get_entry(writer.name)
    await index.put(entry)
    hits = await index.search("draft release notes")
    ```
"""

from typing import TYPE_CHECKING

from agentconnect.index.models import IndexSearchHit, IndexSettings

if TYPE_CHECKING:
    from agentconnect.index.client import IndexClient
    from agentconnect.index.service import create_index_app

__all__ = [
    "IndexClient",
    "IndexSearchHit",
    "IndexSettings",
    "create_index_app",
]

_LAZY = {
    "IndexClient": ("agentconnect.index.client", "IndexClient"),
    "create_index_app": ("agentconnect.index.service", "create_index_app"),
}


def __getattr__(name: str) -> object:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    import importlib

    return getattr(importlib.import_module(module_name), attr)
