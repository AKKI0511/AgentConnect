"""Pluggable embedding backends for a Team Directory.

Profiles are embedded on join and when they change. ``find`` embeds the
query and ranks with a dot product. Nothing here talks to a vector database.

    async def embed_with_my_model(texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    team = await Team("content-squad", embeddings=embed_with_my_model).start()

``"auto"`` (the default) picks a hosted API when a key is already configured,
a local ONNX model when ``agentconnect[embeddings]`` is installed, and a
hashed n-gram vector otherwise. Search still works with no extra packages
and no API key.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import math
import os
import re
from typing import Any, Awaitable, Callable, Protocol, Sequence, Union

logger = logging.getLogger(__name__)

HASHED_DIM = 384
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"

EmbedFn = Callable[
    [Sequence[str]],
    Union[Sequence[Sequence[float]], Awaitable[Sequence[Sequence[float]]]],
]
EmbeddingsArg = Union[str, EmbedFn, "Embedder"]

_WORD = re.compile(r"[a-z0-9]+")
_OPENAI_KEY_VARS = ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")


class Embedder(Protocol):
    """Turns texts into L2-normalized vectors in one shared space."""

    name: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per string, in the same order."""


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return ``vector`` scaled to unit length. A zero vector stays zero."""
    total = math.sqrt(sum(value * value for value in vector))
    if total == 0.0:
        return [0.0 for _ in vector]
    return [value / total for value in vector]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Dot product of two equal-length vectors. Callers pass unit vectors."""
    return sum(a * b for a, b in zip(left, right))


class HashedEmbedder:
    """Deterministic n-gram embedding. No network, no extra packages.

    Used when ``embeddings="none"`` and as the ``auto`` fallback. Ranking
    follows overlapping words and character trigrams, so a query that names
    a Skill still surfaces that Agent.
    """

    name = "hashed"
    dim = HASHED_DIM

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Hash each string into a 384-dimension unit vector."""
        return [_hash_text(text, self.dim) for text in texts]


class CallableEmbedder:
    """Wrap a user function as an :class:`Embedder`.

    The function receives ``list[str]`` and returns one vector per string.
    Sync and async callables both work.
    """

    def __init__(self, fn: EmbedFn, *, name: str = "custom") -> None:
        """Bind ``fn`` as the embedding implementation."""
        self._fn = fn
        self.name = name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Call the wrapped function and L2-normalize each row."""
        result: Any = self._fn(list(texts))
        if inspect.isawaitable(result):
            result = await result
        rows = list(result)
        if len(rows) != len(texts):
            raise ValueError("embedder must return one vector per text")
        normalized: list[list[float]] = []
        for row in rows:
            normalized.append(l2_normalize([float(value) for value in row]))
        return normalized


class OpenAIEmbedder:
    """Hosted embeddings through the OpenAI client already in core deps."""

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL) -> None:
        """Use ``model``. ``text-embedding-3-*`` requests 384 dimensions."""
        self._model = model
        self.name = f"openai:{model}"
        self._client: Any = None

    def _client_obj(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI()
        return self._client

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Call the OpenAI embeddings API."""
        if not texts:
            return []
        kwargs: dict[str, Any] = {"model": self._model, "input": list(texts)}
        if self._model.startswith("text-embedding-3"):
            kwargs["dimensions"] = HASHED_DIM
        response = await self._client_obj().embeddings.create(**kwargs)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [l2_normalize(list(item.embedding)) for item in ordered]


class LiteLLMEmbedder:
    """Hosted embeddings through LiteLLM when that package is installed."""

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL) -> None:
        """Use LiteLLM model id ``model``."""
        self._model = model
        self.name = f"litellm:{model}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Call ``litellm.aembedding``."""
        if not texts:
            return []
        import litellm

        response = await litellm.aembedding(model=self._model, input=list(texts))
        data = getattr(response, "data", None) or response["data"]
        vectors: list[list[float]] = []
        for item in data:
            embedding = item["embedding"] if isinstance(item, dict) else item.embedding
            vectors.append(l2_normalize([float(value) for value in embedding]))
        return vectors


class FastEmbedEmbedder:
    """Local ONNX embeddings through ``fastembed``. Does not import torch."""

    def __init__(self, model: str = DEFAULT_FASTEMBED_MODEL) -> None:
        """Load ``model`` on first embed (about 50MB for the default)."""
        self._model_name = model
        self.name = f"fastembed:{model}"
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Run the ONNX model on a worker thread."""
        if not texts:
            return []
        model = self._load()
        payload = list(texts)

        def _run() -> list[list[float]]:
            return [list(map(float, vector)) for vector in model.embed(payload)]

        vectors = await asyncio.to_thread(_run)
        return [l2_normalize(vector) for vector in vectors]


class AutoEmbedder:
    """Pick a backend on first use, then keep it until it fails.

    Order: hosted API when a key is configured, then ``fastembed``, then
    hashed. A failed hosted call falls back to local embeddings so ``find``
    keeps working after a key is removed.
    """

    def __init__(self) -> None:
        """Create an unresolved auto backend."""
        self._inner: Embedder | None = None

    @property
    def name(self) -> str:
        """Active backend name, or ``auto`` before the first embed."""
        if self._inner is None:
            return "auto"
        return self._inner.name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed with the selected backend, falling back on failure."""
        inner = self._inner or _select_auto_backend()
        try:
            result = await inner.embed(texts)
            self._inner = inner
            return result
        except Exception:
            if getattr(inner, "name", "") == HashedEmbedder.name:
                raise
            logger.warning(
                "embedding backend %s failed; falling back to hashed",
                getattr(inner, "name", type(inner).__name__),
                exc_info=True,
            )
            self._inner = HashedEmbedder()
            return await self._inner.embed(texts)


def resolve_embedder(spec: EmbeddingsArg) -> Embedder:
    """Turn a Team ``embeddings=`` value into an :class:`Embedder`.

    Strings:

    - ``auto`` (default)
    - ``none`` / ``hashed``
    - ``fastembed`` or ``fastembed:<model>``
    - ``openai`` or ``openai:<model>``
    - ``litellm`` or ``litellm:<model>``
    """
    if isinstance(spec, str):
        return _from_string(spec)
    embed = getattr(spec, "embed", None)
    if embed is not None and not isinstance(spec, (bytes, bytearray)):
        return spec  # type: ignore[return-value]
    if callable(spec):
        return CallableEmbedder(spec)
    raise TypeError("embeddings must be a spec string, a callable, or an Embedder")


def _from_string(spec: str) -> Embedder:
    raw = spec.strip()
    if not raw:
        raise ValueError("embeddings spec must not be empty")
    key, _, model = raw.partition(":")
    key = key.lower()
    model = model.strip()
    if key == "auto":
        return AutoEmbedder()
    if key in {"none", "hashed"}:
        return HashedEmbedder()
    if key == "fastembed":
        return FastEmbedEmbedder(model or DEFAULT_FASTEMBED_MODEL)
    if key == "openai":
        return OpenAIEmbedder(model or DEFAULT_OPENAI_MODEL)
    if key == "litellm":
        return LiteLLMEmbedder(model or DEFAULT_OPENAI_MODEL)
    raise ValueError(f"unknown embeddings spec {spec!r}")


def _select_auto_backend() -> Embedder:
    if _pytest_blocks_hosted():
        return HashedEmbedder()
    if _has_openai_key():
        if _module_available("litellm"):
            logger.info("Directory embeddings: litellm (%s)", DEFAULT_OPENAI_MODEL)
            return LiteLLMEmbedder(DEFAULT_OPENAI_MODEL)
        logger.info("Directory embeddings: openai (%s)", DEFAULT_OPENAI_MODEL)
        return OpenAIEmbedder(DEFAULT_OPENAI_MODEL)
    if _module_available("fastembed"):
        logger.info("Directory embeddings: fastembed (%s)", DEFAULT_FASTEMBED_MODEL)
        return FastEmbedEmbedder(DEFAULT_FASTEMBED_MODEL)
    logger.info("Directory embeddings: hashed (no API key, no fastembed)")
    return HashedEmbedder()


def _pytest_blocks_hosted() -> bool:
    return (
        "PYTEST_CURRENT_TEST" in os.environ
        and os.environ.get("AGENTCONNECT_TEST_EMBEDDINGS") != "hosted"
    )


def _has_openai_key() -> bool:
    return any(os.environ.get(name) for name in _OPENAI_KEY_VARS)


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _hash_text(text: str, dim: int) -> list[float]:
    vector = [0.0] * dim
    lowered = text.lower()
    padded = f" {lowered} "
    for index in range(max(0, len(padded) - 2)):
        vector[_bucket(padded[index : index + 3], dim)] += 1.0
    for word in _WORD.findall(lowered):
        vector[_bucket(f"w:{word}", dim)] += 2.0
        if len(word) >= 4:
            vector[_bucket(f"p:{word[:4]}", dim)] += 1.5
    return l2_normalize(vector)


def _bucket(token: str, dim: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % dim
