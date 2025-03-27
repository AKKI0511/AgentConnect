"""
Capability discovery functionality for the AgentConnect framework.

This module provides functions for searching and discovering agent capabilities,
including semantic search using embeddings and simpler string matching methods.
"""

# Standard library imports
import logging
from typing import Dict, List, Set, Tuple

# Absolute imports from agentconnect package
from agentconnect.core.registry.registration import AgentRegistration

# Set up logging
logger = logging.getLogger("CapabilityDiscovery")


def check_semantic_search_requirements() -> bool:
    """
    Check if the required packages for semantic search are installed.

    Returns:
        True if the required packages are installed, False otherwise
    """
    try:
        return True
    except ImportError as e:
        logger.warning(f"Missing package for semantic search: {str(e)}")
        logger.warning(
            "To enable semantic search, install required packages: pip install langchain-huggingface sentence-transformers"
        )
        return False


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple string similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0 and 1
    """
    # This is a very basic implementation
    # In a production system, you would use proper embeddings or NLP techniques
    words1 = set(text1.split())
    words2 = set(text2.split())

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
    import numpy as np

    dot_product = np.dot(vec1, vec2)
    norm_a = np.linalg.norm(vec1)
    norm_b = np.linalg.norm(vec2)
    return dot_product / (norm_a * norm_b)


class CapabilityDiscoveryService:
    """
    Service for discovering agent capabilities through various search methods.

    This class provides methods for finding agents based on their capabilities,
    including exact string matching and semantic search.
    """

    def __init__(self):
        """Initialize the capability discovery service."""
        self._capability_embeddings_cache = {}
        self._embeddings_model = None

    async def initialize_embeddings_model(self):
        """
        Initialize the embeddings model for semantic search.

        This should be called after agents have been registered to
        precompute embeddings for all existing capabilities.
        """
        try:
            if check_semantic_search_requirements():
                from langchain_huggingface import HuggingFaceEmbeddings

                logger.info("Initializing embeddings model for semantic search...")
                self._embeddings_model = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    cache_folder="./.cache/huggingface/embeddings",  # Cache embeddings locally
                )
                self._capability_embeddings_cache = {}
                logger.info("Embeddings model initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize embeddings model: {str(e)}")

    async def update_capability_embeddings_cache(
        self, registration: AgentRegistration
    ) -> None:
        """
        Update the cache of capability embeddings for a registration.

        Args:
            registration: Registration information for the agent
        """
        try:
            # Skip if no capabilities or embeddings model not initialized
            if not registration.capabilities or not self._embeddings_model:
                return

            # Prepare capability texts for batch embedding
            capability_texts = []
            capability_keys = []

            for capability in registration.capabilities:
                capability_text = f"{capability.name} {capability.description}"
                cache_key = f"{registration.agent_id}:{capability.name}"
                capability_texts.append(capability_text)
                capability_keys.append(cache_key)

            # Batch compute embeddings
            if capability_texts:
                embeddings = self._embeddings_model.embed_documents(capability_texts)

                # Store in cache
                for i, cache_key in enumerate(capability_keys):
                    self._capability_embeddings_cache[cache_key] = embeddings[i]

            logger.debug(
                f"Updated capability embeddings cache for agent: {registration.agent_id}"
            )
        except Exception as e:
            logger.warning(f"Error updating capability embeddings cache: {str(e)}")

    def clear_agent_embeddings_cache(self, agent_id: str) -> None:
        """
        Clear the embeddings cache for a specific agent.

        Args:
            agent_id: ID of the agent to clear cache for
        """
        # Find and remove all cache entries for this agent
        keys_to_remove = [
            key
            for key in self._capability_embeddings_cache.keys()
            if key.startswith(f"{agent_id}:")
        ]

        for key in keys_to_remove:
            del self._capability_embeddings_cache[key]

        logger.debug(f"Cleared embeddings cache for agent: {agent_id}")

    async def precompute_all_capability_embeddings(
        self, agent_registrations: Dict[str, AgentRegistration]
    ) -> None:
        """
        Precompute embeddings for all existing capabilities.

        Args:
            agent_registrations: Dictionary of agent registrations
        """
        try:
            if not self._embeddings_model or not agent_registrations:
                return

            logger.info("Precomputing embeddings for all existing capabilities...")

            # Process agents in batches to avoid memory issues
            batch_size = 10
            agent_ids = list(agent_registrations.keys())

            for i in range(0, len(agent_ids), batch_size):
                batch_agent_ids = agent_ids[i : i + batch_size]

                for agent_id in batch_agent_ids:
                    registration = agent_registrations[agent_id]
                    await self.update_capability_embeddings_cache(registration)

            logger.info(
                f"Precomputed embeddings for {len(self._capability_embeddings_cache)} capabilities"
            )
        except Exception as e:
            logger.warning(f"Error precomputing capability embeddings: {str(e)}")

    async def find_by_capability_name(
        self,
        capability_name: str,
        agent_registrations: Dict[str, AgentRegistration],
        capabilities_index: Dict[str, Set[str]],
    ) -> List[AgentRegistration]:
        """
        Find agents by capability name (simple string matching).

        Args:
            capability_name: Name of the capability to search for
            agent_registrations: Dictionary of agent registrations
            capabilities_index: Index of agent capabilities

        Returns:
            List of agent registrations with the specified capability
        """
        logger.debug(f"Searching agents with capability: {capability_name}")
        agent_ids = capabilities_index.get(capability_name, set())
        return [
            agent_registrations[agent_id]
            for agent_id in agent_ids
            if agent_id in agent_registrations
        ]

    async def find_by_capability_semantic(
        self,
        capability_description: str,
        agent_registrations: Dict[str, AgentRegistration],
    ) -> List[Tuple[AgentRegistration, float]]:
        """
        Find agents by capability description using semantic search.

        Args:
            capability_description: Description of the capability to search for
            agent_registrations: Dictionary of agent registrations

        Returns:
            List of tuples containing agent registrations and similarity scores
        """
        logger.debug(
            f"Searching agents with capability description: {capability_description}"
        )
        results = []

        # Check if required packages are installed
        if check_semantic_search_requirements():
            try:
                # Try to use embeddings if available
                from langchain_huggingface import HuggingFaceEmbeddings

                # Initialize embeddings model with caching if not already done
                if not self._embeddings_model:
                    try:
                        self._embeddings_model = HuggingFaceEmbeddings(
                            model_name="sentence-transformers/all-MiniLM-L6-v2",
                            cache_folder="./.cache/huggingface/embeddings",  # Cache embeddings locally
                        )
                        logger.info(
                            "Initialized HuggingFaceEmbeddings model for semantic search"
                        )
                    except Exception as e:
                        logger.error(f"Failed to initialize embeddings model: {str(e)}")
                        raise

                # Get embedding for the query
                query_embedding = self._embeddings_model.embed_query(
                    capability_description
                )

                # Check if we have a cache of capability embeddings
                if self._capability_embeddings_cache:
                    # Use the cache for faster processing
                    for agent_id, registration in agent_registrations.items():
                        highest_similarity = 0.0

                        for capability in registration.capabilities:
                            cache_key = f"{agent_id}:{capability.name}"
                            if cache_key in self._capability_embeddings_cache:
                                # Get the cached embedding
                                capability_embedding = (
                                    self._capability_embeddings_cache[cache_key]
                                )
                                similarity = cosine_similarity(
                                    query_embedding, capability_embedding
                                )
                                highest_similarity = max(highest_similarity, similarity)

                        if (
                            highest_similarity > 0.5
                        ):  # Lower threshold for more lenient matching
                            results.append((registration, highest_similarity))
                else:
                    # Fallback to computing embeddings on the fly
                    # Prepare for batch processing
                    capability_texts = []
                    capability_registrations = []

                    for agent_id, registration in agent_registrations.items():
                        for capability in registration.capabilities:
                            capability_text = (
                                f"{capability.name} {capability.description}"
                            )
                            capability_texts.append(capability_text)
                            capability_registrations.append((registration, capability))

                    # Batch process all capability embeddings at once
                    if capability_texts:
                        capability_embeddings = self._embeddings_model.embed_documents(
                            capability_texts
                        )

                        # Calculate cosine similarity for all capabilities
                        for i, (registration, _) in enumerate(capability_registrations):
                            similarity = cosine_similarity(
                                query_embedding, capability_embeddings[i]
                            )
                            if (
                                similarity > 0.5
                            ):  # Lower threshold for more lenient matching
                                results.append((registration, similarity))

                # Sort by similarity score (highest first)
                results.sort(key=lambda x: x[1], reverse=True)

                # Remove duplicates (keep highest score for each agent)
                unique_results = []
                seen_agent_ids = set()
                for registration, score in results:
                    if registration.agent_id not in seen_agent_ids:
                        unique_results.append((registration, score))
                        seen_agent_ids.add(registration.agent_id)

                return unique_results
            except Exception as e:
                logger.warning(
                    f"Error using embeddings for semantic search: {str(e)}. Falling back to simple similarity."
                )
                # Fall through to simple similarity

        # Fallback to simple string similarity
        for agent_id, registration in agent_registrations.items():
            for capability in registration.capabilities:
                # Simple string similarity check
                similarity = calculate_similarity(
                    capability_description.lower(),
                    f"{capability.name} {capability.description}".lower(),
                )
                if similarity > 0.3:  # Arbitrary threshold
                    results.append((registration, similarity))
                    break  # Only count each agent once

        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        return results
