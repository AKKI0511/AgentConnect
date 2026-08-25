"""Optional index service and client for published directories."""

from typing import Any

__all__ = ["RegistryAPIClient"]


def __getattr__(name: str) -> Any:
    if name == "RegistryAPIClient":
        from agentconnect.index.client import RegistryAPIClient

        return RegistryAPIClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
