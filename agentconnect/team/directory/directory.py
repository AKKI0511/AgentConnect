"""Local Team Directory: member Profiles, stored vectors, ranked ``find``.

The Directory lists this Team's Memberships only. It does not search other
Teams and it does not use a vector database. Vectors sit in the Team Store
beside Memberships.

    from agentconnect.team import Team

    team = await Team("content-squad").start()
    await researcher.join(team)
    found = await researcher.find("someone who can review a contract")
    found["matches"][0]["address"]
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Mapping, Sequence

from agentconnect.core.directory import DirectoryMatch, FindResult
from agentconnect.team.codec import canonical_json
from agentconnect.team.directory.embedder import Embedder, cosine, l2_normalize
from agentconnect.team.store.base import Store

logger = logging.getLogger(__name__)

MAX_FIND_LIMIT = 100
_VECTOR_KEY = "dirvec:{name}"


class Directory:
    """Rank this Team's members for a natural-language query.

    The Runtime owns one Directory per Team. Pass ``embeddings=`` to
    ``Team`` to choose a backend. Most callers only use ``agent.find``.
    """

    def __init__(self, store: Store, embedder: Embedder) -> None:
        """Bind to ``store`` and ``embedder``. Vectors use keys ``dirvec:<name>``."""
        self._store = store
        self._embedder = embedder

    @property
    def backend_name(self) -> str:
        """Name of the embedding backend currently selected."""
        return self._embedder.name

    async def upsert(self, name: str, profile: Mapping[str, Any]) -> None:
        """Embed ``profile`` and store the vector when it changed."""
        await self._embed_member(name, profile, force=False)

    async def drop(self, name: str) -> None:
        """Remove the stored vector for ``name``."""
        await self._store.delete(_VECTOR_KEY.format(name=name))

    async def search(
        self,
        query: str,
        members: Sequence[Mapping[str, Any]],
        *,
        exclude_address: str,
        limit: int | None,
        detail: str,
    ) -> FindResult:
        """Rank ``members`` for ``query`` and return light or full cards.

        Excludes ``exclude_address``. Omitting ``limit`` returns every
        remaining member, at most :data:`MAX_FIND_LIMIT`.
        """
        candidates = [
            member
            for member in members
            if member.get("address") != exclude_address and member.get("profile")
        ]
        if not candidates:
            return FindResult(matches=[])

        query_vectors = await self._embedder.embed([query])
        query_vector = query_vectors[0]
        backend = self._embedder.name
        scored: list[tuple[float, str, Mapping[str, Any]]] = []
        for member in candidates:
            name = str(member["name"])
            profile = member["profile"]
            vector = await self._vector_for(name, profile, backend, query_vector)
            score = cosine(query_vector, vector) if vector else 0.0
            scored.append((score, str(member["address"]), member))
        scored.sort(key=lambda item: (-item[0], item[1]))
        cap = MAX_FIND_LIMIT if limit is None else limit
        matches: list[DirectoryMatch] = [
            _match_card(member, detail=detail) for _, _, member in scored[:cap]
        ]
        return FindResult(matches=matches)

    async def _vector_for(
        self,
        name: str,
        profile: Mapping[str, Any],
        backend: str,
        query_vector: Sequence[float],
    ) -> list[float]:
        record = await self._load_vector(name)
        fingerprint = _fingerprint(profile, backend)
        if (
            record is not None
            and record.get("backend") == backend
            and record.get("fingerprint") == fingerprint
            and len(record.get("vector") or []) == len(query_vector)
        ):
            return [float(value) for value in record["vector"]]
        return await self._embed_member(name, profile, force=True)

    async def _embed_member(
        self, name: str, profile: Mapping[str, Any], *, force: bool
    ) -> list[float]:
        backend = self._embedder.name
        if not force and backend != "auto":
            record = await self._load_vector(name)
            fingerprint = _fingerprint(profile, backend)
            if (
                record is not None
                and record.get("backend") == backend
                and record.get("fingerprint") == fingerprint
            ):
                return [float(value) for value in record["vector"]]
        vectors = await self._embedder.embed([profile_text(profile)])
        vector = l2_normalize(vectors[0])
        backend = self._embedder.name
        fingerprint = _fingerprint(profile, backend)
        await self._store.put(
            _VECTOR_KEY.format(name=name),
            {"backend": backend, "fingerprint": fingerprint, "vector": vector},
        )
        return vector

    async def _load_vector(self, name: str) -> dict[str, Any] | None:
        record = await self._store.get(_VECTOR_KEY.format(name=name))
        if not isinstance(record, dict):
            return None
        return record


def profile_text(profile: Mapping[str, Any]) -> str:
    """Flatten a discovery Profile into the string that gets embedded."""
    parts: list[str] = [str(profile.get("summary") or "")]
    description = profile.get("description")
    if description:
        parts.append(str(description))
    for skill in profile.get("skills") or []:
        if not isinstance(skill, Mapping):
            continue
        parts.append(f"{skill.get('name') or ''}. {skill.get('description') or ''}")
        parts.extend(str(example) for example in skill.get("examples") or [])
        tags = skill.get("tags") or []
        if tags:
            parts.append(" ".join(str(tag) for tag in tags))
    tags = profile.get("tags") or []
    if tags:
        parts.append(" ".join(str(tag) for tag in tags))
    return "\n".join(part for part in parts if part).strip()


def _fingerprint(profile: Mapping[str, Any], backend: str) -> str:
    payload = canonical_json({"backend": backend, "profile": dict(profile)})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _match_card(member: Mapping[str, Any], *, detail: str) -> DirectoryMatch:
    profile = member["profile"]
    data: dict[str, Any] = {
        "address": str(member["address"]),
        "summary": str(profile["summary"]),
        "skill_names": [str(skill["name"]) for skill in profile.get("skills") or []],
    }
    tags = profile.get("tags")
    if tags:
        data["tags"] = [str(tag) for tag in tags]
    if detail == "full":
        data["agent_did"] = str(member["agent_did"])
        data["profile"] = dict(profile)
    return DirectoryMatch.model_validate(data)
