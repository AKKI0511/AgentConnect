"""Persistence used only by the Team Runtime.

A Store holds Memberships, Sessions, Mailboxes, Messages, Tickets, and
Thread history. Agents never talk to it. Memory is the default for a
process-local Team. Redis keeps that state across a Runtime restart.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Store(ABC):
    """Key-value document store plus sets, used by one Team Runtime."""

    persistence: str

    @abstractmethod
    async def open(self) -> None:
        """Connect and prepare the backend."""

    @abstractmethod
    async def close(self) -> None:
        """Release backend resources."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return the JSON-compatible value at ``key``, or None."""

    @abstractmethod
    async def put(self, key: str, value: Any) -> None:
        """Write a JSON-compatible value at ``key``."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove ``key`` if it exists."""

    @abstractmethod
    async def set_add(self, key: str, member: str) -> None:
        """Add ``member`` to the set at ``key``."""

    @abstractmethod
    async def set_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the set at ``key``."""

    @abstractmethod
    async def set_members(self, key: str) -> list[str]:
        """Return the members of the set at ``key``."""

    async def exists(self, key: str) -> bool:
        """Return True when ``key`` has a value."""
        return await self.get(key) is not None

    async def ping(self) -> None:
        """Confirm the backend is reachable. Memory stores no-op."""

    async def clear(self) -> None:
        """Delete every key owned by this store. Used by tests."""
