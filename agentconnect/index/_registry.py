"""Private in-memory roster for one Index process."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from agentconnect.index.models import (
    AgentRegistration,
    IndexQuery,
    IndexSearchHit,
    RegistrationUpdate,
)
from agentconnect.team.directory.embedder import FastEmbedEmbedder, HashedEmbedder


class _Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class DuplicateRegistration(Exception):
    """A record with this agent_id is already stored."""


@dataclass
class _Slot:
    registration: AgentRegistration
    vector: list[float]


def _search_text(registration: AgentRegistration) -> str:
    parts = [
        registration.name or "",
        registration.summary or "",
        registration.description or "",
    ]
    for skill in registration.skills:
        parts.append(skill.name)
        parts.append(skill.description)
    parts.extend(registration.tags)
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


def _detach(registration: AgentRegistration, *, drop_secret: bool) -> AgentRegistration:
    cloned = registration.model_copy(deep=True)
    if drop_secret and cloned.identity.private_key is not None:
        cloned.identity = replace(cloned.identity, private_key=None)
    return cloned


class Registry:
    """Records and vectors owned by one Index process."""

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

    async def get_registration(self, agent_id: str) -> AgentRegistration | None:
        async with self._lock:
            slot = self._slots.get(agent_id)
            if slot is None:
                return None
            return _detach(slot.registration, drop_secret=False)

    async def list_registrations(self) -> list[AgentRegistration]:
        async with self._lock:
            return [
                _detach(slot.registration, drop_secret=False)
                for slot in self._slots.values()
            ]

    async def register(self, registration: AgentRegistration) -> AgentRegistration:
        async with self._lock:
            if registration.agent_id in self._slots:
                raise DuplicateRegistration(registration.agent_id)
            stored = _detach(registration, drop_secret=True)
            vector = await self._vector_for(stored)
            self._slots[stored.agent_id] = _Slot(stored, vector)
            return _detach(stored, drop_secret=False)

    async def update(
        self, agent_id: str, updates: RegistrationUpdate
    ) -> AgentRegistration | None:
        async with self._lock:
            slot = self._slots.get(agent_id)
            if slot is None:
                return None
            candidate = _apply(slot.registration, updates)
            vector = await self._vector_for(candidate)
            self._slots[agent_id] = _Slot(candidate, vector)
            return _detach(candidate, drop_secret=False)

    async def unregister(self, agent_id: str) -> bool:
        async with self._lock:
            if agent_id not in self._slots:
                return False
            del self._slots[agent_id]
            return True

    async def search(self, query: IndexQuery) -> list[IndexSearchHit]:
        async with self._lock:
            snapshot = [
                (
                    _detach(slot.registration, drop_secret=False),
                    list(slot.vector),
                )
                for slot in self._slots.values()
            ]
        required = set(query.tags)
        if required:
            snapshot = [item for item in snapshot if required.issubset(item[0].tags)]
        if not snapshot:
            return []
        (query_vector,) = await self._embedder.embed([query.query])
        ranked = [
            IndexSearchHit(
                registration=registration,
                score=_cosine(query_vector, vector),
            )
            for registration, vector in snapshot
        ]
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return ranked[: query.limit]

    async def _vector_for(self, registration: AgentRegistration) -> list[float]:
        (vector,) = await self._embedder.embed([_search_text(registration)])
        return [float(value) for value in vector]


def _apply(
    current: AgentRegistration, updates: RegistrationUpdate
) -> AgentRegistration:
    patch = updates.model_dump(exclude_unset=True)
    data = current.model_dump()
    data.update(patch)
    data["identity"] = copy.deepcopy(current.identity)
    return AgentRegistration.model_validate(data)
