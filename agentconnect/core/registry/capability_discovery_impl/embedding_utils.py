"""
Embedding utilities for capability discovery.

This module provides functions related to embeddings generation and similarity calculations.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional
from langchain_huggingface import HuggingFaceEmbeddings

# Configure logger
logger = logging.getLogger("CapabilityDiscovery.EmbeddingUtils")


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
        logger.warning(f"Missing base packages for semantic search: {str(e)}")
        logger.warning(
            "To enable semantic search, install required packages: pip install langchain-core numpy"
        )
        return available_backends

    # Check for embedding model
    try:
        # Import inside function to prevent lint errors
        from langchain_huggingface import HuggingFaceEmbeddings  # noqa: F401

        available_backends["embedding_model"] = True
    except ImportError as e:
        logger.warning(f"Missing embedding model: {str(e)}")
        logger.warning(
            "To enable semantic search, install required packages: pip install langchain-huggingface sentence-transformers"
        )

    # Check for Qdrant backend
    try:
        # Import inside function to prevent lint errors
        from qdrant_client import QdrantClient  # noqa: F401
        from qdrant_client.http import models as qdrant_models  # noqa: F401

        available_backends["qdrant"] = True
    except ImportError as e:
        logger.warning(f"Qdrant vector store not available: {str(e)}")
        logger.warning(
            "To enable Qdrant vector search, install: pip install qdrant-client"
        )

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
    config: Dict[str, Any],
) -> Optional[HuggingFaceEmbeddings]:
    """
    Create a HuggingFace embeddings model with the given configuration.

    Args:
        config: Dictionary containing configuration for embeddings model

    Returns:
        HuggingFace embeddings model or None if initialization failed
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        # Get model name from config or use default
        model_name = config.get("model_name", "sentence-transformers/all-mpnet-base-v2")

        logger.info(
            f"Initializing embeddings model {model_name} for semantic search..."
        )

        # Create embeddings model with caching
        cache_folder = config.get("cache_folder", "./.cache/huggingface/embeddings")

        # Try with explicit model_kwargs and encode_kwargs first
        try:
            embeddings_model = HuggingFaceEmbeddings(
                model_name=model_name,
                cache_folder=cache_folder,
                model_kwargs={"device": "cpu", "revision": "main"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("Embeddings model initialized with explicit parameters")
            return embeddings_model
        except Exception as model_error:
            logger.warning(
                f"First embedding initialization attempt failed: {str(model_error)}"
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

                logger.info(
                    "Initialized embeddings using pre-loaded sentence transformer model"
                )
                return embeddings_model
            except Exception as fallback_error:
                # If that fails too, try with minimal parameters
                logger.warning(
                    f"Fallback embedding initialization failed: {str(fallback_error)}"
                )

                # Last attempt with minimal configuration
                try:
                    embeddings_model = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",  # Try with a smaller model
                    )

                    logger.info(
                        "Initialized embeddings with minimal configuration and smaller model"
                    )
                    return embeddings_model
                except Exception as minimal_error:
                    logger.error(
                        f"All embedding initialization attempts failed: {str(minimal_error)}"
                    )
                    return None
    except Exception as e:
        logger.error(f"Failed to initialize embeddings model: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return None
