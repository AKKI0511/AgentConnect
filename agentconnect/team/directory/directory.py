"""Local Team Directory: member Profiles, stored vectors, ranked ``find``.

The Directory lists this Team's Memberships only. It does not search other
Teams and it does not use a vector database. Vectors sit in the Team Store
beside Memberships. One ``find`` ranks in one embedding space.

    from agentconnect.team import Team

    team = await Team("content-squad").start()
    await researcher.join(team)
    found = await researcher.find("someone who can review a contract")
    found.matches[0].address
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from agentconnect.core.directory import DirectoryMatch, FindResult
from agentconnect.team.codec import canonical_json
from agentconnect.team.directory.embedder import (
    Embedder,
    HashedEmbedder,
    _OwnedPool,
    as_unit_vector,
    char_windows,
    cosine,
    input_char_limit,
    max_batch,
    mean_pool,
    normalize_rows,
)
from agentconnect.team.directory.tokens import EmbeddingSetupError
from agentconnect.team.store.base import Store

logger = logging.getLogger(__name__)

MAX_FIND_LIMIT = 100
_VECTOR_KEY = "dirvec:{name}"
_SPACE_KEY = "dirspace"
_SPACE_PROBE = "agentconnect directory embedding space"
# Internal search-text layout. Changing this rebuilds stored vectors.
_REPRESENTATION = "t2"
_SCORE_OFFLOAD_MIN = 16


class _EmbeddingFailed(Exception):
    """The active backend did not return usable vectors."""


@dataclass(frozen=True)
class _Space:
    id: str
    backend: str
    dim: int


class Directory:
    """Rank this Team's members for a natural-language query.

    The Runtime owns one Directory per Team. Pass ``embeddings=`` to
    ``Team`` to choose a backend. Most callers only use ``agent.find``.
    """

    def __init__(self, store: Store, embedder: Embedder) -> None:
        """Bind to ``store`` and ``embedder``. Vectors use keys ``dirvec:<name>``."""
        self._store = store
        self._active = embedder
        self._fallback = False
        self._space: _Space | None = None
        self._lock = asyncio.Lock()
        self._instance_nonce = secrets.token_hex(8)
        self._cpu = _OwnedPool(label="ac-dir-cpu")

    @property
    def backend_name(self) -> str:
        """Name of the embedding backend currently selected."""
        return self._active.name

    @property
    def using_fallback(self) -> bool:
        """True after a configured backend failed and hashed ranking took over."""
        return self._fallback

    async def upsert(self, name: str, profile: Mapping[str, Any]) -> None:
        """Embed ``profile`` and store the vector when it changed."""
        async with self._lock:
            try:
                await self._embed_member(name, profile, force=False)
            except _EmbeddingFailed:
                if not self._activate_fallback():
                    raise
                await self._embed_member(name, profile, force=True)

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
        remaining member, at most :data:`MAX_FIND_LIMIT`. Every match in
        the result is ranked in one embedding space.
        """
        candidates = [
            member
            for member in members
            if member.get("address") != exclude_address and member.get("profile")
        ]
        if not candidates:
            return FindResult(matches=[])

        async with self._lock:
            try:
                return await self._rank_locked(
                    query, candidates, limit=limit, detail=detail
                )
            except _EmbeddingFailed:
                if not self._activate_fallback():
                    raise
                return await self._rank_locked(
                    query, candidates, limit=limit, detail=detail
                )

    def _activate_fallback(self) -> bool:
        if self._fallback or self._active.name == HashedEmbedder.name:
            return False
        logger.warning(
            "embedding backend %s failed; ranking with hashed fallback",
            self._active.name,
            exc_info=True,
        )
        self._active = HashedEmbedder()
        self._fallback = True
        self._space = None
        return True

    async def _rank_locked(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        limit: int | None,
        detail: str,
    ) -> FindResult:
        space = await self._ensure_space()
        query_vector = await self._embed_query(query, expected_dim=space.dim)
        keys = [_VECTOR_KEY.format(name=str(member["name"])) for member in candidates]
        records = await self._store.get_many(keys)
        fingerprints = [_fingerprint(member["profile"]) for member in candidates]
        vectors: list[list[float] | None] = []
        missing: list[int] = []
        for index, record in enumerate(records):
            vector = _usable_vector(record, space, fingerprints[index])
            vectors.append(vector)
            if vector is None:
                missing.append(index)
        if missing:
            batch = max_batch(self._active)
            for start in range(0, len(missing), batch):
                group = missing[start : start + batch]
                profiles = [candidates[index]["profile"] for index in group]
                fresh = await self._embed_profiles(profiles, expected_dim=space.dim)
                for index, vector in zip(group, fresh, strict=True):
                    member = candidates[index]
                    await self._store.put(
                        _VECTOR_KEY.format(name=str(member["name"])),
                        {
                            "space": space.id,
                            "fingerprint": fingerprints[index],
                            "vector": vector,
                        },
                    )
                    vectors[index] = vector
                if start + batch < len(missing):
                    await asyncio.sleep(0)
        resolved: list[list[float]] = []
        addresses: list[str] = []
        for member, vector in zip(candidates, vectors, strict=True):
            if vector is None:
                raise RuntimeError("Directory ranking missed a candidate vector")
            resolved.append(vector)
            addresses.append(str(member["address"]))
        scored = await self._score(query_vector, resolved, addresses)
        by_address = {str(member["address"]): member for member in candidates}
        cap = MAX_FIND_LIMIT if limit is None else limit
        matches: list[DirectoryMatch] = [
            _match_card(by_address[address], detail=detail)
            for _, address in scored[:cap]
        ]
        return FindResult(matches=matches)

    async def _score(
        self,
        query_vector: Sequence[float],
        vectors: Sequence[Sequence[float]],
        addresses: Sequence[str],
    ) -> list[tuple[float, str]]:
        if len(vectors) != len(addresses):
            raise RuntimeError("Directory ranking missed a candidate vector")
        if len(vectors) >= _SCORE_OFFLOAD_MIN:
            return await self._cpu.run(
                _score_rows, list(query_vector), list(vectors), list(addresses)
            )
        return _score_rows(query_vector, vectors, addresses)

    async def _embed_member(
        self, name: str, profile: Mapping[str, Any], *, force: bool
    ) -> list[float]:
        space = await self._ensure_space()
        fingerprint = _fingerprint(profile)
        if not force:
            record = await self._store.get(_VECTOR_KEY.format(name=name))
            vector = _usable_vector(record, space, fingerprint)
            if vector is not None:
                return vector
        vector = (await self._embed_profiles([profile], expected_dim=space.dim))[0]
        await self._store.put(
            _VECTOR_KEY.format(name=name),
            {"space": space.id, "fingerprint": fingerprint, "vector": vector},
        )
        return vector

    async def _ensure_space(self) -> _Space:
        if self._space is not None:
            return self._space
        probe = (await self._embed_texts([_SPACE_PROBE]))[0]
        backend = self._active.name
        dim = len(probe)
        space = _Space(
            id=_space_id(backend, dim, probe, self._instance_nonce),
            backend=backend,
            dim=dim,
        )
        stored = await self._store.get(_SPACE_KEY)
        if not (isinstance(stored, dict) and stored.get("id") == space.id):
            await self._store.put(
                _SPACE_KEY,
                {"id": space.id, "backend": backend, "dim": dim},
            )
        self._space = space
        return space

    async def _embed_query(self, query: str, *, expected_dim: int) -> list[float]:
        limit = input_char_limit(self._active)
        windows = char_windows(query, limit) if limit is not None else [query]
        rows = await self._embed_texts(windows, expected_dim=expected_dim)
        return rows[0] if len(rows) == 1 else mean_pool(rows)

    async def _embed_profiles(
        self,
        profiles: Sequence[Mapping[str, Any]],
        *,
        expected_dim: int,
    ) -> list[list[float]]:
        grouped = [
            profile_windows(profile, input_char_limit(self._active))
            for profile in profiles
        ]
        flat = [window for group in grouped for window in group]
        rows = await self._embed_texts(flat, expected_dim=expected_dim)
        pooled: list[list[float]] = []
        cursor = 0
        for group in grouped:
            next_cursor = cursor + len(group)
            pooled.append(
                rows[cursor]
                if next_cursor - cursor == 1
                else mean_pool(rows[cursor:next_cursor])
            )
            cursor = next_cursor
        return pooled

    async def _embed_texts(
        self, texts: Sequence[str], *, expected_dim: int | None = None
    ) -> list[list[float]]:
        payload = list(texts)
        if not payload:
            return []
        batch = max_batch(self._active)
        out: list[list[float]] = []
        for index in range(0, len(payload), batch):
            chunk = payload[index : index + batch]
            try:
                rows = await self._active.embed(chunk)
                out.extend(normalize_rows(rows, chunk, expected_dim=expected_dim))
            except EmbeddingSetupError:
                raise
            except _EmbeddingFailed:
                raise
            except Exception as exc:
                raise _EmbeddingFailed(str(exc) or type(exc).__name__) from exc
            if index + batch < len(payload):
                await asyncio.sleep(0)
        return out


def profile_text(profile: Mapping[str, Any]) -> str:
    """Flatten a discovery Profile into the string that gets embedded."""
    return "\n".join(_profile_units(profile)).strip()


def profile_windows(profile: Mapping[str, Any], limit: int | None) -> list[str]:
    """Bounded Profile windows for one embedding space.

    When ``limit`` is omitted, the whole Profile is one window and the
    embedder owns token splitting. Otherwise later Skills keep their own
    character windows. The packing is an implementation detail.
    """
    units = _profile_units(profile)
    if limit is None:
        text = "\n".join(units).strip()
        return [text] if text else [""]
    packed: list[str] = []
    buf = ""
    for unit in units:
        if len(unit) > limit:
            if buf:
                packed.append(buf)
                buf = ""
            packed.extend(char_windows(unit, limit))
            continue
        candidate = unit if not buf else f"{buf}\n{unit}"
        if len(candidate) <= limit:
            buf = candidate
        else:
            packed.append(buf)
            buf = unit
    if buf:
        packed.append(buf)
    return packed or [""]


def _profile_units(profile: Mapping[str, Any]) -> list[str]:
    units: list[str] = []
    head_parts = [str(profile.get("summary") or "")]
    description = profile.get("description")
    if description:
        head_parts.append(str(description))
    tags = profile.get("tags") or []
    if tags:
        head_parts.append(" ".join(str(tag) for tag in tags))
    head = "\n".join(part for part in head_parts if part).strip()
    if head:
        units.append(head)
    for skill in profile.get("skills") or []:
        if not isinstance(skill, Mapping):
            continue
        skill_parts = [f"{skill.get('name') or ''}. {skill.get('description') or ''}"]
        skill_parts.extend(str(example) for example in skill.get("examples") or [])
        skill_tags = skill.get("tags") or []
        if skill_tags:
            skill_parts.append(" ".join(str(tag) for tag in skill_tags))
        text = "\n".join(part for part in skill_parts if part).strip()
        if text:
            units.append(text)
    return units


def _fingerprint(profile: Mapping[str, Any]) -> str:
    payload = canonical_json({"profile": dict(profile)})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _space_id(backend: str, dim: int, probe: Sequence[float], nonce: str) -> str:
    if _stable_backend(backend):
        return f"{backend}:{dim}:{_REPRESENTATION}"
    digest = hashlib.sha256()
    digest.update(backend.encode("utf-8"))
    digest.update(b":")
    digest.update(nonce.encode("ascii"))
    digest.update(b":")
    digest.update(str(dim).encode("ascii"))
    digest.update(b":")
    digest.update(_REPRESENTATION.encode("ascii"))
    digest.update(b":")
    for value in probe:
        digest.update(f"{float(value):.6f}".encode("ascii"))
    return f"{backend}:{digest.hexdigest()[:16]}:{_REPRESENTATION}"


def _stable_backend(backend: str) -> bool:
    return backend == "hashed" or backend.startswith(
        ("openai:", "litellm:", "fastembed:")
    )


def _usable_vector(record: Any, space: _Space, fingerprint: str) -> list[float] | None:
    if not isinstance(record, dict):
        return None
    if record.get("space") != space.id:
        return None
    if record.get("fingerprint") != fingerprint:
        return None
    try:
        return as_unit_vector(record.get("vector"), expected_dim=space.dim)
    except (TypeError, ValueError):
        return None


def _score_rows(
    query_vector: Sequence[float],
    vectors: Sequence[Sequence[float]],
    addresses: Sequence[str],
) -> list[tuple[float, str]]:
    scored = [
        (cosine(query_vector, vector), address)
        for vector, address in zip(vectors, addresses, strict=True)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored


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
