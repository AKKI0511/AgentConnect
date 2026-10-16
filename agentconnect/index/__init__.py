"""Optional Index of agent records you submit yourself.

A Team Directory lists members of one Team. Submit an
[`AgentRegistration`][agentconnect.index.models.AgentRegistration] to an
Index, then search the records that process is holding. A search hit
is not a Team address.

Install `agentconnect[index]`. Start
[`create_index_app`][agentconnect.index.service.create_index_app] with
`python -m agentconnect.index.service`. It listens on loopback and reads
[`IndexSettings`][agentconnect.index.models.IndexSettings]. Records
disappear when the process stops. `model_name` is `hashed` unless you
set a fastembed model id. A model that cannot load stops the process.

Examples:
    The Index is already running at `http://127.0.0.1:8000`.

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
        await client.register(registration)
        hits = await client.search(IndexQuery(query="release notes"))
        if hits:
            print(hits[0].registration.name, hits[0].score)
    ```
"""

from typing import TYPE_CHECKING

from agentconnect.index.models import (
    AgentRegistration,
    IndexQuery,
    IndexSearchHit,
    IndexSettings,
    RegistrationUpdate,
)

if TYPE_CHECKING:
    from agentconnect.index.client import IndexClient
    from agentconnect.index.service import create_index_app

__all__ = [
    "AgentRegistration",
    "IndexClient",
    "IndexQuery",
    "IndexSearchHit",
    "IndexSettings",
    "RegistrationUpdate",
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
