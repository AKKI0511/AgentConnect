"""Embedding helpers for the optional Index registry.

The Index does not import LangChain or sentence-transformers. Hashed n-grams
always work. ``fastembed`` is used when the extra is installed and the
configured model is not ``hashed``.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional, Protocol, Sequence, Union

from agentconnect.config.vector import VectorSearchSettings
from agentconnect.team.directory.embedder import HASHED_DIM, _hash_text

logger = logging.getLogger(__name__)


class Embeddings(Protocol):
    """Sync embedder used by Qdrant indexing. ``embed_query`` returns one vector."""

    def embed_query(self, text: str) -> list[float]:
        """Embed one query string."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed many documents, in order."""


class HashedEmbeddings:
    """Deterministic n-gram vectors. No extra packages."""

    def embed_query(self, text: str) -> list[float]:
        """Hash ``text`` into a 384-dimension unit vector."""
        return _hash_text(text, HASHED_DIM)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Hash each string."""
        return [_hash_text(text, HASHED_DIM) for text in texts]


class FastEmbedSync:
    """Local ONNX embeddings through ``fastembed``."""

    def __init__(self, model_name: str) -> None:
        """Load ``model_name`` through fastembed."""
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)

    def embed_query(self, text: str) -> list[float]:
        """Embed one query."""
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed many documents."""
        return [list(map(float, vector)) for vector in self._model.embed(list(texts))]


def check_semantic_search_requirements() -> Dict[str, bool]:
    """Return which Index search backends are importable."""
    available = {
        "qdrant": False,
        "base_requirements": True,
        "embedding_model": True,
    }
    try:
        from qdrant_client import QdrantClient  # noqa: F401
        from qdrant_client.http import models as qdrant_models  # noqa: F401

        available["qdrant"] = True
    except ImportError:
        logger.warning("Qdrant is not installed. pip install 'agentconnect[index]'")
    return available


def calculate_similarity(text1: str, text2: str) -> float:
    """Jaccard similarity of whitespace-split tokens, case-insensitive."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.0
    return len(words1.intersection(words2)) / len(words1.union(words2))


def cosine_similarity(vec1: Sequence[float], vec2: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors."""
    left = [float(value) for value in vec1]
    right = [float(value) for value in vec2]
    dot = sum(a * b for a, b in zip(left, right))
    norm_a = math.sqrt(sum(a * a for a in left))
    norm_b = math.sqrt(sum(b * b for b in right))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def create_embeddings(
    config: Union[VectorSearchSettings, None] = None,
) -> Optional[Embeddings]:
    """Return a sync embedder. Hashed when no local model is configured."""
    cfg = config if config is not None else VectorSearchSettings()
    model_name = (cfg.model_name or "hashed").strip()
    if model_name.lower() in {"hashed", "none", ""}:
        return HashedEmbeddings()
    try:
        return FastEmbedSync(model_name)
    except Exception:
        logger.warning(
            "fastembed model %s failed; using hashed embeddings",
            model_name,
            exc_info=True,
        )
        return HashedEmbeddings()


def create_huggingface_embeddings(
    config: Union[VectorSearchSettings, None] = None,
) -> Optional[Embeddings]:
    """Return :func:`create_embeddings`. Name kept for Index call sites."""
    return create_embeddings(config)
