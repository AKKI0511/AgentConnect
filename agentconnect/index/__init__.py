"""Optional published-directory Index, separate from a Team Directory.

A Team Directory lists members of one Team. The Index aggregates
directories that Teams publish so an Agent can find Teams nobody
configured locally. It is not required for Agents on the same Team.

`RegistryAPIClient` is the HTTP client. Run the Index process with
`agentconnect.index.service.create_registry_api_app` and
`RegistryAPISettings` from the environment. Registration types live in
`agentconnect.index.types`.

Install `agentconnect[index]`. This package talks to Qdrant and is not
the Team Runtime search path.

Examples:
    Construct the Index client (the Index process must already be up):

    ```python
    from agentconnect.index import RegistryAPIClient

    client = RegistryAPIClient(base_url="http://127.0.0.1:8000")
    ```
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentconnect.index.client import RegistryAPIClient

__all__ = ["RegistryAPIClient"]


def __getattr__(name: str) -> object:
    if name == "RegistryAPIClient":
        from agentconnect.index.client import RegistryAPIClient

        return RegistryAPIClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
