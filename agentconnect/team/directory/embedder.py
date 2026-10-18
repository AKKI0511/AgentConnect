"""Embedding backends you can pass to `Team`.

`HashedEmbedder` stays on this machine. `FastEmbedEmbedder` uses a local ONNX model when
`agentconnect[embeddings]` is installed. `OpenAIEmbedder` and
`LiteLLMEmbedder` send Profile text to a hosted model, and only when
you select them.

Examples:
    Pass an existing encoder's async method as a callable:

    ```python
    from agentconnect.team import Team
    from agentconnect.team.directory.embedder import HashedEmbedder

    encoder = HashedEmbedder()
    team = Team("content-squad", embeddings=encoder.embed)
    ```
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
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    ParamSpec,
    Protocol,
    Sequence,
    TypeGuard,
    TypeVar,
    Union,
)
from functools import partial

if TYPE_CHECKING:
    from httpx import AsyncClient
    from fastembed import TextEmbedding
    from tiktoken import Encoding

from agentconnect.team.directory.tokens import (
    OPENAI_INPUT_TOKENS,
    OPENAI_REQUEST_TOKENS,
    encoding_for_hosted_model,
    hosted_litellm_limits,
    local_content_tokens,
    pack_token_batches,
    split_token_windows,
    token_windows,
)

_P = ParamSpec("_P")
_T = TypeVar("_T")

logger = logging.getLogger(__name__)

__all__ = [
    "EmbedFn",
    "Embedder",
    "EmbeddingsArg",
    "FastEmbedEmbedder",
    "HashedEmbedder",
    "LiteLLMEmbedder",
    "OpenAIEmbedder",
]

_HASHED_DIM = 384
_DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
_DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"
_DEFAULT_BATCH = 32
_OPENAI_BATCH = 128
_HASHED_BATCH = 8

EmbedFn = Callable[
    [list[str]],
    Union[Sequence[Sequence[float]], Awaitable[Sequence[Sequence[float]]]],
]
"""A callable returning one finite, nonempty vector per input, in input order.

All calls must use the same dimension and embedding space. The callable
may return rows directly or an awaitable. The Team normalizes its rows.
"""
EmbeddingsArg = Union[str, EmbedFn, "Embedder"]
"""Team embedding selection: backend string, sync/async `EmbedFn`, or `Embedder`."""

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
        self.pending = 0
        self.peak_pending = 0
        weakref.finalize(self, pool.shutdown, wait=False, cancel_futures=True)

    async def run(
        self, fn: Callable[_P, _T], *args: _P.args, **kwargs: _P.kwargs
    ) -> _T:
        self.pending += 1
        if self.pending > self.peak_pending:
            self.peak_pending = self.pending
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self._pool, partial(fn, *args, **kwargs))
        finally:
            self.pending -= 1


class Embedder(Protocol):
    """Supply custom search embeddings to `Team(embeddings=backend)`.

    Implement `embed` and the three attributes below. Return finite,
    nonempty vectors in one consistent dimension and embedding space,
    across both Profile and query calls. Normalize nonzero vectors to
    unit length; zero vectors remain zero. Return an empty list for an
    empty input. The Team may call the backend from concurrent joins or
    searches; handle any resources your implementation owns.
    """

    if TYPE_CHECKING:

        @property
        def name(self) -> str:
            """Stable backend/model name identifying the embedding space."""
    else:
        # Read capability for typing; retain a plain runtime declaration so
        # existing explicit subclasses can initialize their own name field.
        name: str
        """Stable backend/model name identifying the embedding space."""
    input_char_limit: int | None
    """Maximum characters per input, or None for no character bound."""
    max_batch: int
    """Positive maximum number of strings accepted by one `embed` call."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized vectors in input order; zero vectors stay zero."""


def _as_unit_vector(vector: object, *, expected_dim: int | None = None) -> list[float]:
    """Return `vector` as a finite unit vector, or raise `ValueError`.

    Args:
        vector: Numeric components.
        expected_dim: When set, reject a different length.

    Returns:
        An L2-normalized copy of `vector`.
    """
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
        raise ValueError("embedding vector must be a sequence of numbers")
    values: list[float] = []
    for value in vector:
        # Cached vectors already contain plain floats. Avoid repeating two
        # isinstance checks and float conversion for every stored component.
        if type(value) is float:
            number = value
        else:
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
    return _l2_normalize(values)


def _normalize_rows(
    rows: Sequence[Sequence[float]],
    texts: Sequence[object],
    *,
    expected_dim: int | None = None,
) -> list[list[float]]:
    """Validate one vector per text, one dimension, and finite values.

    Args:
        rows: Embedding rows from a backend.
        texts: Strings that produced `rows`.
        expected_dim: When set, every row must have this length.

    Returns:
        L2-normalized rows in the same order.

    Raises:
        ValueError: Count, dimension, or values are invalid.
    """
    if len(rows) != len(texts):
        raise ValueError("embedder must return one vector per text")
    out: list[list[float]] = []
    dim = expected_dim
    for row in rows:
        vector = _as_unit_vector(row, expected_dim=dim)
        if dim is None:
            dim = len(vector)
        out.append(vector)
    return out


def _l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return `vector` scaled to unit length. A zero vector stays zero.

    Args:
        vector: Numeric components.
    """
    total = math.sqrt(sum(value * value for value in vector))
    if total == 0.0:
        return [0.0 for _ in vector]
    return [value / total for value in vector]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Dot product of two equal-length vectors. Callers pass unit vectors.

    Args:
        left: First unit vector.
        right: Second unit vector.

    Raises:
        ValueError: The vectors have different lengths.
    """
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    return sum(a * b for a, b in zip(left, right, strict=True))


def _mean_pool(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Average unit vectors and L2-normalize the result.

    Args:
        vectors: One or more same-dimension unit vectors.

    Raises:
        ValueError: `vectors` is empty or dimensions differ.
    """
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
    return _l2_normalize([value * scale for value in acc])


def _char_windows(text: str, limit: int) -> list[str]:
    """Split `text` into chunks of at most `limit` characters.

    Args:
        text: Input to split.
        limit: Maximum characters per chunk. Must be at least 1.

    Returns:
        One or more windows covering `text`.
    """
    if limit < 1:
        raise ValueError("input limit must be positive")
    stripped = text.strip()
    if not stripped:
        return [""]
    if len(stripped) <= limit:
        return [stripped]
    return [stripped[index : index + limit] for index in range(0, len(stripped), limit)]


def _input_char_limit(embedder: object) -> int | None:
    """Character budget for one backend input, or `None` when unbounded.

    Args:
        embedder: Embedding backend.
    """
    value = getattr(embedder, "input_char_limit", None)
    if value is None:
        return None
    return max(1, int(value))


def _max_batch(embedder: object) -> int:
    """Maximum texts one `embed` call should receive.

    Args:
        embedder: Embedding backend.
    """
    value = getattr(embedder, "max_batch", _DEFAULT_BATCH)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return _DEFAULT_BATCH


class HashedEmbedder:
    """Local embeddings based on shared words and character trigrams.

    Requires no extra packages or network access. Select this with
    `embeddings="none"` or pass an instance to `Team`. Search also uses
    this backend if a configured encoder fails. Neural embeddings can
    match related meanings that share few words.
    """

    name = "hashed"
    """Backend and model name for this embedding space."""
    dim = _HASHED_DIM
    """Number of components in each output vector."""
    input_char_limit: int | None = None
    """None: this backend imposes no character bound."""
    max_batch = _HASHED_BATCH
    """Maximum strings per Team embedding call."""

    def __init__(self) -> None:
        self._work: _OwnedPool | None = None

    def _pool(self) -> _OwnedPool:
        if self._work is None:
            self._work = _OwnedPool(label="ac-embed-hash")
        return self._work

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized 384-component vectors in input order.

        An empty string produces a zero vector.
        """
        payload = list(texts)
        if not payload:
            return []
        return await self._pool().run(_hash_texts, payload, self.dim)


class _CallableEmbedder:
    """Wrap a user function as an `Embedder`.

    The function receives `list[str]` and returns one vector per string.
    Coroutine functions run on the event loop. Other callables run on this
    embedder's worker. If that worker returns an awaitable, it is awaited
    here. Two different callables are different embedding spaces even when
    both would otherwise be named `custom`.
    """

    input_char_limit: int | None = None
    max_batch = _DEFAULT_BATCH

    def __init__(self, fn: EmbedFn, *, name: str = "custom") -> None:
        """Bind `fn` as the embedding implementation.

        Args:
            fn: Callable `(list[str]) -> list[list[float]]`, sync or async.
            name: Backend name recorded on stored vectors. Defaults to
                `custom`.
        """
        self._fn = fn
        self.name = name
        self._work: _OwnedPool | None = None

    def _pool(self) -> _OwnedPool:
        if self._work is None:
            self._work = _OwnedPool(label="ac-embed-fn")
        return self._work

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Call the wrapped function and L2-normalize each row.

        Args:
            texts: Profile or query strings.
        """
        payload = list(texts)
        if not payload:
            return []
        if _is_coroutine_callable(self._fn):
            raw: Sequence[Sequence[float]] | Awaitable[Sequence[Sequence[float]]] = (
                self._fn(payload)
            )
        else:
            raw = await self._pool().run(self._fn, payload)
        if inspect.isawaitable(raw):
            raw = await raw
        return _normalize_rows(list(raw), payload)


class OpenAIEmbedder:
    """Send Profile and query text to OpenAI for embeddings.

    Requires `agentconnect[openai]`. Missing tiktoken raises a setup
    error without switching to hashed search.
    """

    input_char_limit: int | None = None
    """None: this backend imposes no character bound."""
    max_batch = _OPENAI_BATCH
    """Maximum strings per Team embedding call."""
    input_token_limit = OPENAI_INPUT_TOKENS
    """Maximum tokens per hosted input window."""
    request_token_limit = OPENAI_REQUEST_TOKENS
    """Maximum tokens per hosted request."""

    def __init__(self, model: str = _DEFAULT_OPENAI_MODEL) -> None:
        """Use 384 dimensions for `text-embedding-3-*` models."""
        self._model = model
        self._encoding = encoding_for_hosted_model(model)
        self.name: str = f"openai:{model}"
        """Backend and model name for this embedding space."""
        self._client: AsyncClient | None = None

    def _client_obj(self) -> AsyncClient:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts using the configured model and `OPENAI_API_KEY`.

        Long inputs are split to the model limit and combined into one
        vector per string.

        Returns:
            Normalized vectors in input order; zero vectors stay zero.

        Raises:
            RuntimeError: No API key is set.
            httpx.HTTPError: The provider request fails.
            ValueError: The provider returns invalid vectors.
        """
        payload = list(texts)
        if not payload:
            return []
        return await _embed_token_bounded(
            payload,
            encoding=self._encoding,
            per_input_tokens=self.input_token_limit,
            request_tokens=self.request_token_limit,
            batch=self.max_batch,
            embed_chunk=self._embed_request,
        )

    async def _embed_request(self, windows: list[list[int]]) -> list[list[float]]:
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        body: dict[str, object] = {"model": self._model, "input": windows}
        expected_dim: int | None = None
        if self._model.startswith("text-embedding-3"):
            body["dimensions"] = _HASHED_DIM
            expected_dim = _HASHED_DIM
        response = await self._client_obj().post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()["data"]
        ordered = sorted(data, key=lambda item: item["index"])
        rows = [list(item["embedding"]) for item in ordered]
        return _normalize_rows(rows, windows, expected_dim=expected_dim)


class LiteLLMEmbedder:
    """Send Profile and query text to OpenAI or Azure through LiteLLM.

    Requires `agentconnect[aiagent,openai]`. Other embedding providers
    are refused.
    """

    input_char_limit: int | None = None
    """None: this backend imposes no character bound."""
    max_batch = _OPENAI_BATCH
    """Maximum strings per Team embedding call."""
    input_token_limit = OPENAI_INPUT_TOKENS
    """Maximum tokens per hosted input window."""
    request_token_limit = OPENAI_REQUEST_TOKENS
    """Maximum tokens per hosted request."""

    def __init__(self, model: str = _DEFAULT_OPENAI_MODEL) -> None:
        input_tokens, request_tokens = hosted_litellm_limits(model)
        self._model = model
        self._encoding = encoding_for_hosted_model(model)
        self.input_token_limit = input_tokens
        self.request_token_limit = request_tokens
        self.name: str = f"litellm:{model}"
        """Backend and model name for this embedding space."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts with the configured LiteLLM provider.

        Set credentials for that provider before calling. Long inputs
        are split to the model limit and combined into one vector per
        string. Provider errors propagate to direct callers.

        Returns:
            Normalized vectors in input order; zero vectors stay zero.

        Raises:
            ImportError: LiteLLM is not installed.
            ValueError: The provider returns invalid vectors.
        """
        payload = list(texts)
        if not payload:
            return []
        return await _embed_token_bounded(
            payload,
            encoding=self._encoding,
            per_input_tokens=self.input_token_limit,
            request_tokens=self.request_token_limit,
            batch=self.max_batch,
            embed_chunk=self._embed_request,
        )

    async def _embed_request(self, windows: list[list[int]]) -> list[list[float]]:
        import litellm

        response = await litellm.aembedding(model=self._model, input=windows)
        data = getattr(response, "data", None) or response["data"]
        rows: list[list[float]] = []
        for item in data:
            embedding = item["embedding"] if isinstance(item, dict) else item.embedding
            rows.append(list(embedding))
        return _normalize_rows(rows, windows)


class FastEmbedEmbedder:
    """Embed Profile and query text locally with an ONNX model.

    Requires `agentconnect[embeddings]`. The first call may download
    model files; Profile and query text stay on this machine.
    """

    input_char_limit: int | None = None
    """None: this backend imposes no character bound."""
    max_batch = _DEFAULT_BATCH
    """Maximum strings per Team embedding call."""

    def __init__(self, model: str = _DEFAULT_FASTEMBED_MODEL) -> None:
        self._model_name = model
        self.name: str = f"fastembed:{model}"
        """Backend and model name for this embedding space."""
        self._model: TextEmbedding | None = None
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
        if tokenizer is None:
            raise RuntimeError(
                f"FastEmbed model {self._model_name} did not expose a tokenizer"
            )
        budget = local_content_tokens(tokenizer)
        for index, text in enumerate(texts):
            pieces = token_windows(tokenizer, text, budget)
            for piece in pieces:
                windows.append(piece)
                owners.append(index)
        raw = [list(map(float, vector)) for vector in model.embed(windows)]
        grouped: list[list[list[float]]] = [[] for _ in texts]
        for owner, vector in zip(owners, raw, strict=True):
            grouped[owner].append(vector)
        return [_mean_pool(group) for group in grouped]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts locally, loading the configured model on first use.

        Long inputs are split to the model limit and combined into one
        vector per string.

        Returns:
            Normalized vectors in input order; zero vectors stay zero.

        Raises:
            ImportError: FastEmbed is not installed.
            RuntimeError: The model has no usable tokenizer.
            ValueError: The model returns invalid vectors.
        """
        payload = list(texts)
        if not payload:
            return []
        rows = await self._work.run(self._embed_sync, payload)
        return _normalize_rows(rows, payload)


class _AutoEmbedder:
    """Pick a local backend on first use, then keep it.

    Order: `fastembed` when that extra is installed, otherwise hashed.
    Ambient API keys do not select a hosted backend. Selection, including
    optional-package imports, runs on this instance's worker. A later
    failure is raised so the Directory can rebuild one coherent index
    instead of mixing spaces.
    """

    input_char_limit: int | None = None
    max_batch = _DEFAULT_BATCH

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
        """Active backend name, or `auto` before the first embed."""
        if self._inner is None:
            return "auto"
        return self._inner.name

    def _choose(self) -> Embedder:
        with self._pick:
            if self._inner is None:
                self._inner = _select_auto_backend()
                self.input_char_limit = _input_char_limit(self._inner)
                self.max_batch = _max_batch(self._inner)
            return self._inner

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed with the selected backend. Does not swap after a success.

        Args:
            texts: Profile or query strings.
        """
        if self._inner is None:
            inner = await self._pool().run(self._choose)
        else:
            inner = self._inner
        return await inner.embed(texts)


def _has_embed_method(value: EmbeddingsArg) -> TypeGuard[Embedder]:
    # Match the existing structural extension boundary, including callable backends.
    return getattr(value, "embed", None) is not None and not isinstance(
        value, (bytes, bytearray)
    )


def _resolve_embedder(spec: EmbeddingsArg) -> Embedder:
    """Turn a Team `embeddings=` value into an `Embedder`.

    Strings:

    - `auto` (default): local ONNX when installed, otherwise hashed
    - `none` / `hashed`
    - `fastembed` or `fastembed:<model>`
    - `openai` or `openai:<model>` (explicit hosted; needs tiktoken)
    - `litellm` or `litellm:<model>` (explicit hosted OpenAI/Azure)

    Args:
        spec: Spec string, callable `(list[str]) -> list[list[float]]`,
            or an `Embedder`.

    Returns:
        An embedder ready for Directory ranking.

    Raises:
        TypeError: `spec` is not a string, callable, or Embedder.
        ValueError: The spec string is empty or unknown.
    """
    if isinstance(spec, str):
        return _from_string(spec)
    if _has_embed_method(spec):
        return spec
    if callable(spec):
        return _CallableEmbedder(spec)
    raise TypeError("embeddings must be a spec string, a callable, or an Embedder")


def _from_string(spec: str) -> Embedder:
    raw = spec.strip()
    if not raw:
        raise ValueError("embeddings spec must not be empty")
    key, _, model = raw.partition(":")
    key = key.lower()
    model = model.strip()
    if key == "auto":
        return _AutoEmbedder()
    if key in {"none", "hashed"}:
        return HashedEmbedder()
    if key == "fastembed":
        return FastEmbedEmbedder(model or _DEFAULT_FASTEMBED_MODEL)
    if key == "openai":
        return OpenAIEmbedder(model or _DEFAULT_OPENAI_MODEL)
    if key == "litellm":
        return LiteLLMEmbedder(model or _DEFAULT_OPENAI_MODEL)
    raise ValueError(f"unknown embeddings spec {spec!r}")


def _select_auto_backend() -> Embedder:
    if _pytest_pins_hashed_auto():
        logger.info("Directory embeddings: hashed (pytest auto pin)")
        return HashedEmbedder()
    if _module_available("fastembed"):
        logger.info(
            "Directory embeddings: fastembed (%s); local model files stay on this host",
            _DEFAULT_FASTEMBED_MODEL,
        )
        return FastEmbedEmbedder(_DEFAULT_FASTEMBED_MODEL)
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
    encoding: Encoding,
    per_input_tokens: int,
    request_tokens: int,
    batch: int,
    embed_chunk: Callable[[list[list[int]]], Awaitable[list[list[float]]]],
) -> list[list[float]]:
    groups = [split_token_windows(encoding, text, per_input_tokens) for text in texts]
    flat = [window for group in groups for window in group]
    raw: list[list[float]] = []
    chunks = pack_token_batches(flat, batch=batch, request_tokens=request_tokens)
    for index, chunk in enumerate(chunks):
        raw.extend(await embed_chunk(chunk))
        if index + 1 < len(chunks):
            await asyncio.sleep(0)
    pooled: list[list[float]] = []
    cursor = 0
    for group in groups:
        next_cursor = cursor + len(group)
        pooled.append(_mean_pool(raw[cursor:next_cursor]))
        cursor = next_cursor
    return pooled


def _fastembed_tokenizer(model: object) -> Any:
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


def _hashed_embedding(text: str, dim: int = _HASHED_DIM) -> list[float]:
    """Return the hashed n-gram vector for `text`.

    Args:
        text: Profile or query text to embed.
        dim: Vector length. Defaults to 384.

    Returns:
        A unit-length vector of `dim` floats.
    """
    return _hash_text(text, dim)


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
    return _l2_normalize(vector)


def _bucket(token: str, dim: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % dim
