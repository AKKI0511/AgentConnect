"""
Capability discovery functionality for the AgentConnect framework.

This module provides the main interface for searching and discovering agent capabilities,
including semantic search using embeddings and simpler string matching methods.
"""

from __future__ import annotations

# Standard library imports
import logging
import time
import asyncio
from typing import Dict, List, Set, Tuple, Any, Optional, Union, TYPE_CHECKING, cast

# Avoid importing implementation modules at top-level to prevent optional deps from loading

# Absolute imports from agentconnect package
from agentconnect.index.registry.registration import AgentRegistration
from agentconnect.config.models import VectorSearchSettings
from agentconnect.config import settings as global_settings

# Type-only imports for IDEs and static analysis (no runtime import)
if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings as _Embeddings
    from qdrant_client import QdrantClient as _QdrantClient
    from qdrant_client import AsyncQdrantClient as _AsyncQdrantClient

# Set up logging
logger = logging.getLogger(__name__)


class CapabilityDiscoveryService:
    """
    Service for discovering agent capabilities through various search methods.

    This class provides methods for finding agents based on their capabilities,
    including exact string matching and semantic search using Qdrant vector database.
    """

    # Collection name for agent profiles and capabilities
    # Keep local constant to avoid importing qdrant submodule on import
    COLLECTION_NAME = "agent_capabilities"

    def __init__(
        self,
        vector_search_config: Optional[
            Union[VectorSearchSettings, Dict[str, Any]]
        ] = None,
    ):
        """
        Initialize the capability discovery service.

        Args:
            vector_search_config: Optional vector search configuration. Accepts either a `VectorSearchSettings` instance or a `dict` shaped like the Pydantic model (with `deployment` and `advanced` nested objects).
        """
        self._embeddings_model: Optional[_Embeddings] = None
        self._qdrant_client: Optional[_QdrantClient] = None  # Synchronous Qdrant client
        self._async_qdrant_client: Optional[_AsyncQdrantClient] = (
            None  # Asynchronous Qdrant client
        )
        self._capability_to_agent_map: Dict[str, AgentRegistration] = {}
        if vector_search_config is None:
            self._vector_store_config = global_settings.registry.vector_search
        elif isinstance(vector_search_config, VectorSearchSettings):
            self._vector_store_config = vector_search_config
        else:
            self._vector_store_config = VectorSearchSettings.model_validate(
                vector_search_config
            )
        self._available_backends = {}
        self._vector_store_initialized = asyncio.Event()
        self._vector_store_initialized.clear()
        self._collection_initialized = False

    def _get_batch_size(self) -> int:
        """Resolve batch size from config for backward compatibility.

        Supports both Pydantic model settings and plain dict configs.
        """
        try:
            return self._vector_store_config.advanced.batch_size
        except Exception:
            return 100

    async def initialize_embeddings_model(self):
        """
        Initialize the embeddings model for semantic search and Qdrant client.

        This should be called after agents have been registered to
        precompute embeddings for all existing capabilities.
        """
        start_ts = time.time()
        try:
            # Check which backends are available
            from agentconnect.index.registry.capability_discovery_impl.embedding_utils import (
                check_semantic_search_requirements,
                create_huggingface_embeddings,
            )

            self._available_backends = check_semantic_search_requirements()

            if not self._available_backends["embedding_model"]:
                logger.warning("Embedding model not available")
                return

            if not self._available_backends["qdrant"]:
                logger.warning("Qdrant unavailable; falling back to string search")
                return

            # Initialize embeddings model
            self._embeddings_model = cast(
                "Optional[_Embeddings]",
                create_huggingface_embeddings(self._vector_store_config),
            )
            if not self._embeddings_model:
                logger.warning("Failed to initialize embeddings model")
                return

            # Reset capability map
            self._capability_to_agent_map = {}

            # Initialize Qdrant clients
            from agentconnect.index.registry.capability_discovery_impl.qdrant_client import (
                initialize_qdrant_clients,
                init_qdrant_collection,
            )

            self._qdrant_client, self._async_qdrant_client = cast(
                "Tuple[Optional[_QdrantClient], Optional[_AsyncQdrantClient]]",
                await initialize_qdrant_clients(self._vector_store_config),
            )

            if not self._qdrant_client or not self._async_qdrant_client:
                logger.warning("Failed to initialize Qdrant clients")
                return

            # Initialize Qdrant collection
            self._collection_initialized = await init_qdrant_collection(
                self._async_qdrant_client,
                self._embeddings_model,
                self.COLLECTION_NAME,
                self._vector_store_config,
            )

            if not self._collection_initialized:
                logger.warning("Failed to initialize Qdrant collection")
                return

            duration_s = time.time() - start_ts
            logger.info(
                "Vector components initialized model=%s duration=%.3fs",
                self._vector_store_config.model_name,
                duration_s,
            )
        except Exception as e:
            logger.error("Failed to initialize vector components: %s", e)

    async def update_capability_embeddings_cache(
        self, registration: AgentRegistration
    ) -> None:
        """
        Update capability embeddings for a registration in Qdrant.

        Args:
            registration: Registration information for the agent
        """
        start_ts = time.time()
        try:
            # Skip if embeddings model or clients not initialized
            if not self._embeddings_model or not self._async_qdrant_client:
                logger.warning(
                    "Embeddings model or client not initialized agent_id=%s",
                    registration.agent_id,
                )
                return

            # Update the capability map
            from agentconnect.index.registry.capability_discovery_impl.indexing import (
                update_capability_embeddings,
            )

            self._capability_to_agent_map = await update_capability_embeddings(
                self._async_qdrant_client,
                self.COLLECTION_NAME,
                self._embeddings_model,
                registration,
                self._capability_to_agent_map,
            )
            duration_ms = int((time.time() - start_ts) * 1000.0)
            logger.debug(
                "Updated capability embeddings cache agent_id=%s duration=%dms",
                registration.agent_id,
                duration_ms,
            )
        except Exception as e:
            logger.error(
                "Error updating capability embeddings cache agent_id=%s: %s",
                registration.agent_id,
                e,
            )

    async def clear_agent_embeddings_cache(self, agent_id: str) -> None:
        """
        Clear the embeddings cache for a specific agent from Qdrant.

        Args:
            agent_id: ID of the agent to clear cache for
        """
        if not self._async_qdrant_client or not self._collection_initialized:
            logger.warning(
                "Qdrant not initialized; skipping clear agent_id=%s", agent_id
            )
            return

        start_ts = time.time()
        try:
            # Delete points from Qdrant
            from agentconnect.index.registry.capability_discovery_impl.qdrant_client import (
                delete_points_by_agent_id,
            )

            await delete_points_by_agent_id(
                self._async_qdrant_client, self.COLLECTION_NAME, agent_id
            )

            # Remove agent from capability_to_agent_map
            doc_ids_to_remove = [
                doc_id
                for doc_id in self._capability_to_agent_map.keys()
                if doc_id.startswith(f"{agent_id}_profile")
                or doc_id.startswith(f"{agent_id}:")
            ]

            for doc_id in doc_ids_to_remove:
                del self._capability_to_agent_map[doc_id]

            duration_ms = int((time.time() - start_ts) * 1000.0)
            logger.debug(
                "Cleared agent embeddings agent_id=%s duration=%dms",
                agent_id,
                duration_ms,
            )

        except Exception as e:
            logger.error("Error clearing agent embeddings agent_id=%s: %s", agent_id, e)

    async def precompute_all_capability_embeddings(
        self, agent_registrations: Dict[str, AgentRegistration]
    ) -> None:
        """
        Precompute embeddings for all existing capabilities and store in Qdrant.

        Args:
            agent_registrations: Dictionary of agent registrations
        """
        start_ts = time.time()
        try:
            if (
                not self._embeddings_model
                or not agent_registrations
                or not self._async_qdrant_client
            ):
                logger.warning("Missing components for indexing")
                self._vector_store_initialized.set()  # Signal that initialization is complete (with no data)
                return

            # Make sure collection is initialized
            if not self._collection_initialized:
                from agentconnect.index.registry.capability_discovery_impl.qdrant_client import (
                    init_qdrant_collection,
                )

                self._collection_initialized = await init_qdrant_collection(
                    self._async_qdrant_client,
                    self._embeddings_model,
                    self.COLLECTION_NAME,
                    self._vector_store_config,
                )

                if not self._collection_initialized:
                    logger.error("Failed to initialize Qdrant collection")
                    self._vector_store_initialized.set()
                    return

            # Compute embeddings and store in Qdrant
            from agentconnect.index.registry.capability_discovery_impl.indexing import (
                precompute_all_capability_embeddings as _precompute_all_capability_embeddings,
            )

            capability_to_agent_map, total_points = (
                await _precompute_all_capability_embeddings(
                    self._async_qdrant_client,
                    self.COLLECTION_NAME,
                    self._embeddings_model,
                    agent_registrations,
                    self._get_batch_size(),
                )
            )

            # Update capability map
            self._capability_to_agent_map = capability_to_agent_map

            # Signal that vector store initialization is complete
            self._vector_store_initialized.set()
            duration_ms = int((time.time() - start_ts) * 1000.0)
            logger.debug(
                "Precomputed capability embeddings duration=%dms points_indexed=%d",
                duration_ms,
                total_points,
            )

        except Exception as e:
            logger.error("Error precomputing capability embeddings: %s", e)
            # Make sure to set the event even if initialization fails
            self._vector_store_initialized.set()

    async def find_by_capability_name(
        self,
        capability_name: str,
        agent_registrations: Dict[str, AgentRegistration],
        capabilities_index: Dict[str, Set[str]],
        limit: int = 10,
        similarity_threshold: float = 0.1,
    ) -> List[AgentRegistration]:
        """
        Find agents by capability name (simple string matching).

        Args:
            capability_name: Name of the capability to search for
            agent_registrations: Dictionary of agent registrations
            capabilities_index: Index of agent capabilities
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score to include in results (default: 0.1)

        Returns:
            List of agent registrations with the specified capability
        """
        # If semantic search is available, provide it as a fallback
        semantic_search_func = None
        if (
            self._async_qdrant_client
            and self._embeddings_model
            and self._collection_initialized
        ):
            semantic_search_func = self.find_by_capability_semantic

        # Call the implementation function (boundary logged at service level)
        from agentconnect.index.registry.capability_discovery_impl.search import (
            find_by_capability_name as _find_by_capability_name,
        )

        return await _find_by_capability_name(
            capability_name,
            agent_registrations,
            capabilities_index,
            semantic_search_func,
            limit,
            similarity_threshold,
        )

    async def find_by_capability_semantic(
        self,
        capability_description: str,
        agent_registrations: Dict[str, AgentRegistration],
        limit: int = 10,
        similarity_threshold: float = 0.1,
        filters: Optional[Dict[str, List[str]]] = None,
    ) -> List[Tuple[AgentRegistration, float]]:
        """
        Find agents by capability description using semantic search with metadata filtering.

        Args:
            capability_description: Description of the capability to search for
            agent_registrations: Dictionary of agent registrations
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score to include in results (default: 0.1)
            filters: Optional dictionary for filtering. Keys can include "tags",
                     "organization", "developer", "default_input_modes", "default_output_modes", "auth_schemes".
                     Values are lists of strings to match for the respective key.

        Returns:
            List of tuples containing agent registrations and similarity scores
        """
        # Call the implementation function
        if (
            self._async_qdrant_client
            and self._embeddings_model
            and self._collection_initialized
        ):
            start_ts = time.time()
            from agentconnect.index.registry.capability_discovery_impl.search import (
                search_with_qdrant as _search_with_qdrant,
            )

            results = await _search_with_qdrant(
                self._async_qdrant_client,
                self.COLLECTION_NAME,
                capability_description,
                self._embeddings_model,
                agent_registrations,
                self._capability_to_agent_map,
                limit,
                similarity_threshold,
                filters=filters,
            )
            duration_ms = int((time.time() - start_ts) * 1000.0)
            logger.debug(
                "Vector search completed duration=%dms results=%d",
                duration_ms,
                len(results),
            )
            return results
        else:
            # Fall back to basic string similarity if Qdrant search not available
            from agentconnect.index.registry.capability_discovery_impl.search import (
                fallback_string_search as _fallback_string_search,
            )

            logger.warning("Falling back to string search")
            return await _fallback_string_search(
                capability_description,
                agent_registrations,
                limit,
                similarity_threshold,
                filters=filters,
            )
