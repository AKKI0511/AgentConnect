"""
Embedding utilities for capability discovery.

This module provides functions related to embeddings generation and similarity calculations.
"""

import logging
import numpy as np
from typing import Dict, Optional, Union
from langchain_huggingface import HuggingFaceEmbeddings

# Absolute imports from agentconnect package
from agentconnect.config.models import VectorSearchSettings
from agentconnect.config import settings

# Configure logger (module namespace)
logger = logging.getLogger(__name__)


def check_semantic_search_requirements() -> Dict[str, bool]:
    """
    Check if the required packages for semantic search are installed.

    Returns:
        Dictionary indicating which vector store backends are available
    """
    available_backends = {
        "qdrant": False,
        "base_requirements": False,
        "embedding_model": False,
    }

    # Check for base requirements
    try:
        # Import inside function to prevent lint errors
        import numpy  # noqa: F401
        from langchain_core.documents import Document  # noqa: F401

        available_backends["base_requirements"] = True
    except ImportError as e:
        logger.warning("Missing base packages for semantic search: %s", e)
        return available_backends

    # Check for embedding model
    try:
        # Import inside function to prevent lint errors
        from langchain_huggingface import HuggingFaceEmbeddings  # noqa: F401

        available_backends["embedding_model"] = True
    except ImportError as e:
        logger.warning("Missing embedding model: %s", e)

    # Check for Qdrant backend
    try:
        # Import inside function to prevent lint errors
        from qdrant_client import QdrantClient  # noqa: F401
        from qdrant_client.http import models as qdrant_models  # noqa: F401

        available_backends["qdrant"] = True
    except ImportError as e:
        logger.warning("Qdrant vector store not available: %s", e)

    return available_backends


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple Jaccard similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0 and 1
    """
    # Simple Jaccard similarity implementation (intersection over union)
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return len(intersection) / len(union)


def cosine_similarity(vec1, vec2):
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity between the vectors
    """
    dot_product = np.dot(vec1, vec2)
    norm_a = np.linalg.norm(vec1)
    norm_b = np.linalg.norm(vec2)

    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def create_huggingface_embeddings(
    config: Union[VectorSearchSettings, None] = None,
) -> Optional[HuggingFaceEmbeddings]:
    """
    Create a HuggingFace embeddings model with the given configuration.

    Args:
        config: VectorSearchSettings for embeddings model, or None to use global `settings.registry.vector_search`.

    Returns:
        HuggingFace embeddings model or None if initialization failed
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        if config is None:
            model_name = settings.registry.vector_search.model_name
            cache_folder = settings.registry.vector_search.cache_folder
        else:
            model_name = config.model_name
            cache_folder = config.cache_folder

        # Create embeddings model with caching
        # Try with explicit model_kwargs and encode_kwargs first
        try:
            embeddings_model = HuggingFaceEmbeddings(
                model_name=model_name,
                cache_folder=cache_folder,
                model_kwargs={"device": "cpu", "revision": "main"},
                encode_kwargs={"normalize_embeddings": True},
            )
            return embeddings_model
        except Exception as model_error:
            logger.warning(
                "First embedding initialization attempt failed: %s", model_error
            )

            # Try alternative initialization approach
            try:
                # Import directly from sentence_transformers as fallback
                import sentence_transformers

                # Create the model directly first
                st_model = sentence_transformers.SentenceTransformer(
                    model_name,
                    cache_folder=cache_folder,
                    device="cpu",
                    revision="main",  # Use main branch which is more stable
                )

                # Then create embeddings with the pre-initialized model
                embeddings_model = HuggingFaceEmbeddings(
                    model=st_model, encode_kwargs={"normalize_embeddings": True}
                )
                return embeddings_model
            except Exception as fallback_error:
                # If that fails too, try with minimal parameters
                logger.warning(
                    "Fallback embedding initialization failed: %s", fallback_error
                )

                # Last attempt with minimal configuration
                try:
                    embeddings_model = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",  # Try with a smaller model
                    )
                    return embeddings_model
                except Exception:
                    logger.error(
                        "All embedding initialization attempts failed", exc_info=True
                    )
                    return None
    except Exception:
        logger.error("Failed to initialize embeddings model", exc_info=True)
        return None
