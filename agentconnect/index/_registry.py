"""Private in-memory roster for one Index process."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from agentconnect.core.directory import DirectoryEntry
from agentconnect.index.models import IndexSearchHit
from agentconnect.team.directory.embedder import FastEmbedEmbedder, HashedEmbedder


class _Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass
class _Slot:
    entry: DirectoryEntry
    vector: list[float]


def _search_text(entry: DirectoryEntry) -> str:
    profile = entry.profile
    parts = [profile.summary, profile.description or ""]
    for skill in profile.skills:
        parts.append(skill.name)
        parts.append(skill.description)
        if skill.tags:
            parts.extend(skill.tags)
    if profile.tags:
        parts.extend(profile.tags)
    return "\n".join(part for part in parts if part)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise RuntimeError("Index vectors have different lengths")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(dot / (left_norm * right_norm))


def _detach(entry: DirectoryEntry) -> DirectoryEntry:
    return entry.model_copy(deep=True)


class Registry:
    """Snapshots and vectors owned by one Index process."""

    def __init__(self, model_name: str = "hashed") -> None:
        name = model_name.strip()
        if name.lower() in {"hashed", "none"}:
            self._embedder: _Embedder = HashedEmbedder()
        else:
            self._embedder = FastEmbedEmbedder(name)
        self._lock = asyncio.Lock()
        self._slots: dict[str, _Slot] = {}

    async def open(self) -> None:
        await self._embedder.embed([""])

    async def get(self, address: str) -> DirectoryEntry | None:
        async with self._lock:
            slot = self._slots.get(address)
            if slot is None:
                return None
            return _detach(slot.entry)

    async def put(self, entry: DirectoryEntry) -> DirectoryEntry:
        stored = _detach(entry)
        vector = await self._vector_for(stored)
        async with self._lock:
            self._slots[stored.address] = _Slot(stored, vector)
            return _detach(stored)

    async def delete(self, address: str) -> None:
        async with self._lock:
            self._slots.pop(address, None)

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        tags: Sequence[str] | None = None,
    ) -> list[IndexSearchHit]:
        async with self._lock:
            snapshot = [
                (_detach(slot.entry), list(slot.vector))
                for slot in self._slots.values()
            ]
        required = set(tags or ())
        if required:
            snapshot = [
                item
                for item in snapshot
                if required.issubset(set(item[0].profile.tags or ()))
            ]
        if not snapshot:
            return []
        (query_vector,) = await self._embedder.embed([query])
        ranked = [
            IndexSearchHit(entry=entry, score=_cosine(query_vector, vector))
            for entry, vector in snapshot
        ]
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return ranked[:limit]

    async def _vector_for(self, entry: DirectoryEntry) -> list[float]:
        (vector,) = await self._embedder.embed([_search_text(entry)])
        return [float(value) for value in vector]

    async def list(self) -> list[DirectoryEntry]:
        async with self._lock:
            return [_detach(slot.entry) for slot in self._slots.values()]
