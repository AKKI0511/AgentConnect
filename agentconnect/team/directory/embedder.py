"""Pluggable embedding backends for a Team Directory.

Profiles are embedded on join and when they change. ``find`` embeds the
query and ranks with a dot product. Nothing here talks to a vector database.

    async def embed_with_my_model(texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    team = await Team("content-squad", embeddings=embed_with_my_model).start()

``"auto"`` (the default) uses a local ONNX model when
``agentconnect[embeddings]`` is installed, and hashed n-grams otherwise.
An API key in the environment is not permission to send Profiles or
queries to a hosted embedder. Pass ``embeddings="openai"`` or
``"litellm:<model>"`` to opt in to hosted embeddings.

A backend that fails is not swapped here. The Directory owns fallback so
one ``find`` never mixes two embedding spaces.

Neural backends own token limits. They split a complete input to the
selected model's per-input budget and, for hosted calls, the request
budget. Directory character packing is only for backends that publish a
character limit.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import math
import os
import re
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Protocol, Sequence, Union

from agentconnect.team.directory.tokens import (
    DEFAULT_LOCAL_INPUT_TOKENS,
    OPENAI_INPUT_TOKENS,
    OPENAI_REQUEST_TOKENS,
    estimate_token_windows,
    hosted_token_count,
    hosted_token_windows,
    local_content_tokens,
    pack_token_batches,
    token_windows,
)

logger = logging.getLogger(__name__)

HASHED_DIM = 384
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_BATCH = 32
OPENAI_BATCH = 128
HASHED_BATCH = 8

EmbedFn = Callable[
    [Sequence[str]],
    Union[Sequence[Sequence[float]], Awaitable[Sequence[Sequence[float]]]],
]
EmbeddingsArg = Union[str, EmbedFn, "Embedder"]

_WORD = re.compile(r"[a-z0-9]+")


class _OwnedPool:
    """One worker thread owned by a single embedder instance.

    Serialization stays inside that instance. Another Directory's embedder
    does not share the worker. This is not the event-loop default executor.
    Cancelling the asyncio waiter does not stop the running thread.
    """

    def __init__(self, *, label: str) -> None:
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=label)
        self._pool = pool
        weakref.finalize(self, pool.shutdown, wait=False, cancel_futures=True)

    async def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, fn, *args)


class Embedder(Protocol):
    """Turns texts into L2-normalized vectors in one shared space."""

    name: str
    input_char_limit: int | None
    max_batch: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per string, in the same order."""


def as_unit_vector(
    vector: Sequence[float], *, expected_dim: int | None = None
) -> list[float]:
    """Return ``vector`` as a finite unit vector, or raise ``ValueError``."""
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
        raise ValueError("embedding vector must be a sequence of numbers")
    values: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("embedding values must be finite numbers")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("embedding values must be finite")
        values.append(number)
    if not values:
        raise ValueError("embedding vector must not be empty")
    if expected_dim is not None and len(values) != expected_dim:
        raise ValueError(
            f"embedding dimension {len(values)} does not match {expected_dim}"
        )
    return l2_normalize(values)


def normalize_rows(
    rows: Sequence[Sequence[float]],
    texts: Sequence[str],
    *,
    expected_dim: int | None = None,
) -> list[list[float]]:
    """Validate one vector per text, one dimension, and finite values."""
    if len(rows) != len(texts):
        raise ValueError("embedder must return one vector per text")
    out: list[list[float]] = []
    dim = expected_dim
    for row in rows:
        vector = as_unit_vector(row, expected_dim=dim)
        if dim is None:
            dim = len(vector)
        out.append(vector)
    return out


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return ``vector`` scaled to unit length. A zero vector stays zero."""
    total = math.sqrt(sum(value * value for value in vector))
    if total == 0.0:
        return [0.0 for _ in vector]
    return [value / total for value in vector]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Dot product of two equal-length vectors. Callers pass unit vectors."""
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    return sum(a * b for a, b in zip(left, right, strict=True))


def mean_pool(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Average unit vectors and L2-normalize the result."""
    if not vectors:
        raise ValueError("cannot pool empty vectors")
    if len(vectors) == 1:
        return list(vectors[0])
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vector in vectors:
        if len(vector) != dim:
            raise ValueError("pooled vectors must share a dimension")
        for index, value in enumerate(vector):
            acc[index] += float(value)
    scale = 1.0 / len(vectors)
    return l2_normalize([value * scale for value in acc])


def char_windows(text: str, limit: int) -> list[str]:
    """Split ``text`` into chunks of at most ``limit`` characters."""
    if limit < 1:
        raise ValueError("input limit must be positive")
    stripped = text.strip()
    if not stripped:
        return [""]
    if len(stripped) <= limit:
        return [stripped]
    return [stripped[index : index + limit] for index in range(0, len(stripped), limit)]


def input_char_limit(embedder: Any) -> int | None:
    """Character budget for one backend input, or ``None`` when unbounded."""
    value = getattr(embedder, "input_char_limit", None)
    if value is None:
        return None
    return max(1, int(value))


def max_batch(embedder: Any) -> int:
    """Maximum texts one ``embed`` call should receive."""
    value = getattr(embedder, "max_batch", DEFAULT_BATCH)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_BATCH


class HashedEmbedder:
    """Deterministic n-gram embedding. No network, no extra packages.

    Used when ``embeddings="none"`` and as the Directory availability
    substitute. Ranking follows overlapping words and character trigrams,
    so a query that names a Skill still surfaces that Agent. That is not
    the same quality as a configured neural backend.
    """

    name = "hashed"
    dim = HASHED_DIM
    input_char_limit: int | None = None
    max_batch = HASHED_BATCH

    def __init__(self) -> None:
        """Create a hashed embedder with its own worker."""
        self._work: _OwnedPool | None = None

    def _pool(self) -> _OwnedPool:
        if self._work is None:
            self._work = _OwnedPool(label="ac-embed-hash")
        return self._work

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Hash each string into a 384-dimension unit vector off the loop."""
        payload = list(texts)
        if not payload:
            return []
        return await self._pool().run(_hash_texts, payload, self.dim)


class CallableEmbedder:
    """Wrap a user function as an :class:`Embedder`.

    The function receives ``list[str]`` and returns one vector per string.
    Coroutine functions run on the event loop. Other callables run on this
    embedder's worker. If that worker returns an awaitable, it is awaited
    here. Two different callables are different embedding spaces even when
    both would otherwise be named ``custom``.
    """

    input_char_limit: int | None = None
    max_batch = DEFAULT_BATCH

    def __init__(self, fn: EmbedFn, *, name: str = "custom") -> None:
        """Bind ``fn`` as the embedding implementation."""
        self._fn = fn
        self.name = name
        self._work: _OwnedPool | None = None

    def _pool(self) -> _OwnedPool:
        if self._work is None:
            self._work = _OwnedPool(label="ac-embed-fn")
        return self._work

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Call the wrapped function and L2-normalize each row."""
        payload = list(texts)
        if not payload:
            return []
        if _is_coroutine_callable(self._fn):
            raw: Any = self._fn(payload)
        else:
            raw = await self._pool().run(self._fn, payload)
        if inspect.isawaitable(raw):
            raw = await raw
        return normalize_rows(list(raw), payload)


class OpenAIEmbedder:
    """Hosted embeddings through the OpenAI HTTP API. Uses httpx, not the OpenAI SDK."""

    input_char_limit: int | None = None
    max_batch = OPENAI_BATCH
    input_token_limit = OPENAI_INPUT_TOKENS
    request_token_limit = OPENAI_REQUEST_TOKENS

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL) -> None:
        """Use ``model``. ``text-embedding-3-*`` requests 384 dimensions."""
        self._model = model
        self.name = f"openai:{model}"
        self._client: Any = None

    def _client_obj(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """POST /v1/embeddings. Requires ``OPENAI_API_KEY``."""
        payload = list(texts)
        if not payload:
            return []
        return await _embed_token_bounded(
            payload,
            per_input_tokens=self.input_token_limit,
            request_tokens=self.request_token_limit,
            batch=self.max_batch,
            embed_chunk=self._embed_request,
        )

    async def _embed_request(self, texts: list[str]) -> list[list[float]]:
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        body: dict[str, Any] = {"model": self._model, "input": texts}
        expected_dim: int | None = None
        if self._model.startswith("text-embedding-3"):
            body["dimensions"] = HASHED_DIM
            expected_dim = HASHED_DIM
        response = await self._client_obj().post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()["data"]
        ordered = sorted(data, key=lambda item: item["index"])
        rows = [list(item["embedding"]) for item in ordered]
        return normalize_rows(rows, texts, expected_dim=expected_dim)


class LiteLLMEmbedder:
    """Hosted embeddings through LiteLLM when that package is installed."""

    input_char_limit: int | None = None
    max_batch = OPENAI_BATCH
    input_token_limit = OPENAI_INPUT_TOKENS
    request_token_limit = OPENAI_REQUEST_TOKENS

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL) -> None:
        """Use LiteLLM model id ``model``."""
        self._model = model
        self.name = f"litellm:{model}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Call ``litellm.aembedding``."""
        payload = list(texts)
        if not payload:
            return []
        return await _embed_token_bounded(
            payload,
            per_input_tokens=self.input_token_limit,
            request_tokens=self.request_token_limit,
            batch=self.max_batch,
            embed_chunk=self._embed_request,
        )

    async def _embed_request(self, texts: list[str]) -> list[list[float]]:
        import litellm

        response = await litellm.aembedding(model=self._model, input=texts)
        data = getattr(response, "data", None) or response["data"]
        rows: list[list[float]] = []
        for item in data:
            embedding = item["embedding"] if isinstance(item, dict) else item.embedding
            rows.append(list(embedding))
        return normalize_rows(rows, texts)


class FastEmbedEmbedder:
    """Local ONNX embeddings through ``fastembed``. Does not import torch.

    Installing ``agentconnect[embeddings]`` may download a local model
    snapshot. That is not the same as sending Profile or query text to a
    hosted provider.
    """

    input_char_limit: int | None = None
    max_batch = DEFAULT_BATCH

    def __init__(self, model: str = DEFAULT_FASTEMBED_MODEL) -> None:
        """Load ``model`` on first embed (about 50MB for the default)."""
        self._model_name = model
        self.name = f"fastembed:{model}"
        self._model: Any = None
        self._thread_lock = threading.Lock()
        self._work = _OwnedPool(label="ac-embed-fe")

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        with self._thread_lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(model_name=self._model_name)
            model = self._model
        windows: list[str] = []
        owners: list[int] = []
        tokenizer = _fastembed_tokenizer(model)
        budget = (
            local_content_tokens(tokenizer)
            if tokenizer is not None
            else DEFAULT_LOCAL_INPUT_TOKENS
        )
        for index, text in enumerate(texts):
            if tokenizer is not None:
                pieces = token_windows(tokenizer, text, budget)
            else:
                pieces = estimate_token_windows(text, budget)
            for piece in pieces:
                windows.append(piece)
                owners.append(index)
        raw = [list(map(float, vector)) for vector in model.embed(windows)]
        grouped: list[list[list[float]]] = [[] for _ in texts]
        for owner, vector in zip(owners, raw, strict=True):
            grouped[owner].append(vector)
        return [mean_pool(group) for group in grouped]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Load the ONNX model and embed on this instance's worker."""
        payload = list(texts)
        if not payload:
            return []
        rows = await self._work.run(self._embed_sync, payload)
        return normalize_rows(rows, payload)


class AutoEmbedder:
    """Pick a local backend on first use, then keep it.

    Order: ``fastembed`` when that extra is installed, otherwise hashed.
    Ambient API keys do not select a hosted backend. Selection, including
    optional-package imports, runs on this instance's worker. A later
    failure is raised so the Directory can rebuild one coherent index
    instead of mixing spaces.
    """

    input_char_limit: int | None = None
    max_batch = DEFAULT_BATCH

    def __init__(self) -> None:
        """Create an unresolved auto backend."""
        self._inner: Embedder | None = None
        self._pick = threading.Lock()
        self._work: _OwnedPool | None = None

    def _pool(self) -> _OwnedPool:
        if self._work is None:
            self._work = _OwnedPool(label="ac-embed-auto")
        return self._work

    @property
    def name(self) -> str:
        """Active backend name, or ``auto`` before the first embed."""
        if self._inner is None:
            return "auto"
        return self._inner.name

    def _choose(self) -> Embedder:
        with self._pick:
            if self._inner is None:
                self._inner = _select_auto_backend()
                self.input_char_limit = input_char_limit(self._inner)
                self.max_batch = max_batch(self._inner)
            return self._inner

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed with the selected backend. Does not swap after a success."""
        if self._inner is None:
            inner = await self._pool().run(self._choose)
        else:
            inner = self._inner
        return await inner.embed(texts)


def resolve_embedder(spec: EmbeddingsArg) -> Embedder:
    """Turn a Team ``embeddings=`` value into an :class:`Embedder`.

    Strings:

    - ``auto`` (default): local ONNX when installed, otherwise hashed
    - ``none`` / ``hashed``
    - ``fastembed`` or ``fastembed:<model>``
    - ``openai`` or ``openai:<model>`` (explicit hosted)
    - ``litellm`` or ``litellm:<model>`` (explicit hosted)
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
    if _pytest_pins_hashed_auto():
        logger.info("Directory embeddings: hashed (pytest auto pin)")
        return HashedEmbedder()
    if _module_available("fastembed"):
        logger.info(
            "Directory embeddings: fastembed (%s); local model files stay on this host",
            DEFAULT_FASTEMBED_MODEL,
        )
        return FastEmbedEmbedder(DEFAULT_FASTEMBED_MODEL)
    logger.info("Directory embeddings: hashed (no local ONNX extra)")
    return HashedEmbedder()


def _pytest_pins_hashed_auto() -> bool:
    if "PYTEST_CURRENT_TEST" not in os.environ:
        return False
    allowed = os.environ.get("AGENTCONNECT_TEST_EMBEDDINGS", "").strip().lower()
    return allowed not in {"fastembed", "hosted", "local"}


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _is_coroutine_callable(fn: EmbedFn) -> bool:
    if inspect.iscoroutinefunction(fn):
        return True
    call = getattr(fn, "__call__", None)
    return inspect.iscoroutinefunction(call)


async def _embed_token_bounded(
    texts: list[str],
    *,
    per_input_tokens: int,
    request_tokens: int,
    batch: int,
    embed_chunk: Callable[[list[str]], Awaitable[list[list[float]]]],
) -> list[list[float]]:
    groups = [hosted_token_windows(text, per_input_tokens) for text in texts]
    flat = [window for group in groups for window in group]
    costs = [hosted_token_count(window) for window in flat]
    raw: list[list[float]] = []
    chunks = pack_token_batches(flat, costs, batch=batch, request_tokens=request_tokens)
    for index, chunk in enumerate(chunks):
        raw.extend(await embed_chunk(chunk))
        if index + 1 < len(chunks):
            await asyncio.sleep(0)
    pooled: list[list[float]] = []
    cursor = 0
    for group in groups:
        next_cursor = cursor + len(group)
        pooled.append(mean_pool(raw[cursor:next_cursor]))
        cursor = next_cursor
    return pooled


def _fastembed_tokenizer(model: Any) -> Any:
    for candidate in (
        model,
        getattr(model, "model", None),
        getattr(model, "embedding_model", None),
    ):
        if candidate is None:
            continue
        tokenizer = getattr(candidate, "tokenizer", None)
        if tokenizer is not None and hasattr(tokenizer, "encode"):
            return tokenizer
        nested = getattr(candidate, "model", None)
        nested_tokenizer = getattr(nested, "tokenizer", None) if nested else None
        if nested_tokenizer is not None and hasattr(nested_tokenizer, "encode"):
            return nested_tokenizer
    return None


def _hash_texts(texts: list[str], dim: int) -> list[list[float]]:
    return [_hash_text(text, dim) for text in texts]


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
