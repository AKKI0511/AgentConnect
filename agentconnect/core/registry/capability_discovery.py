"""
Capability discovery functionality for the AgentConnect framework.

This module provides the main interface for searching and discovering agent capabilities,
including semantic search using embeddings and simpler string matching methods.
"""

# Standard library imports
import logging
import asyncio
from typing import Dict, List, Set, Tuple, Any, Optional

# Import from implementation modules
from agentconnect.core.registry.capability_discovery_impl.embedding_utils import (
    check_semantic_search_requirements,
    create_huggingface_embeddings,
)
from agentconnect.core.registry.capability_discovery_impl.qdrant_client import (
    DEFAULT_COLLECTION_NAME,
    initialize_qdrant_clients,
    init_qdrant_collection,
    delete_points_by_agent_id,
)
from agentconnect.core.registry.capability_discovery_impl.search import (
    find_by_capability_name,
    search_with_qdrant,
    fallback_string_search,
)
from agentconnect.core.registry.capability_discovery_impl.indexing import (
    precompute_all_capability_embeddings,
    update_capability_embeddings,
)

# Absolute imports from agentconnect package
from agentconnect.core.registry.registration import AgentRegistration

# Set up logging
logger = logging.getLogger("CapabilityDiscovery")


class CapabilityDiscoveryService:
    """
    Service for discovering agent capabilities through various search methods.

    This class provides methods for finding agents based on their capabilities,
    including exact string matching and semantic search using Qdrant vector database.
    """

    # Collection name for agent profiles and capabilities
    COLLECTION_NAME = DEFAULT_COLLECTION_NAME

    def __init__(self, vector_store_config: Dict[str, Any] = None):
        """
        Initialize the capability discovery service.

        Args:
            vector_store_config: Optional configuration for vector store
                                 Can include 'host', 'port', 'api_key', 'model_name', etc.
        """
        self._embeddings_model = None
        self._qdrant_client = None  # Synchronous Qdrant client
        self._async_qdrant_client = None  # Asynchronous Qdrant client
        self._capability_to_agent_map: Dict[str, AgentRegistration] = {}
        self._vector_store_config = vector_store_config or {}
        self._available_backends = {}
        self._vector_store_initialized = asyncio.Event()
        self._vector_store_initialized.clear()
        self._collection_initialized = False

    async def initialize_embeddings_model(self):
        """
        Initialize the embeddings model for semantic search and Qdrant client.

        This should be called after agents have been registered to
        precompute embeddings for all existing capabilities.
        """
        try:
            # Check which backends are available
            self._available_backends = check_semantic_search_requirements()

            if not self._available_backends["embedding_model"]:
                logger.warning(
                    "Embedding model not available, semantic search will be limited"
                )
                return

            if not self._available_backends["qdrant"]:
                logger.warning(
                    "Qdrant not available, semantic search will fall back to basic similarity"
                )
                return

            # Initialize embeddings model
            self._embeddings_model = create_huggingface_embeddings(
                self._vector_store_config
            )
            if not self._embeddings_model:
                logger.warning("Failed to initialize embeddings model")
                return

            # Reset capability map
            self._capability_to_agent_map = {}

            # Initialize Qdrant clients
            self._qdrant_client, self._async_qdrant_client = (
                await initialize_qdrant_clients(self._vector_store_config)
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

            logger.info("Embeddings model and Qdrant clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())

    async def update_capability_embeddings_cache(
        self, registration: AgentRegistration
    ) -> None:
        """
        Update capability embeddings for a registration in Qdrant.

        Args:
            registration: Registration information for the agent
        """
        try:
            # Skip if embeddings model or clients not initialized
            if not self._embeddings_model or not self._async_qdrant_client:
                logger.warning("Embeddings model or Qdrant client not initialized")
                return

            # Update the capability map
            self._capability_to_agent_map = await update_capability_embeddings(
                self._async_qdrant_client,
                self.COLLECTION_NAME,
                self._embeddings_model,
                registration,
                self._capability_to_agent_map,
            )

        except Exception as e:
            logger.error(f"Error updating capability embeddings: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())

    async def clear_agent_embeddings_cache(self, agent_id: str) -> None:
        """
        Clear the embeddings cache for a specific agent from Qdrant.

        Args:
            agent_id: ID of the agent to clear cache for
        """
        if not self._async_qdrant_client or not self._collection_initialized:
            logger.warning("Qdrant client not initialized, skipping clear operation")
            return

        try:
            # Delete points from Qdrant
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

            logger.info(f"Cleared embeddings for agent: {agent_id}")

        except Exception as e:
            logger.error(f"Error clearing agent embeddings: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())

    async def precompute_all_capability_embeddings(
        self, agent_registrations: Dict[str, AgentRegistration]
    ) -> None:
        """
        Precompute embeddings for all existing capabilities and store in Qdrant.

        Args:
            agent_registrations: Dictionary of agent registrations
        """
        try:
            if (
                not self._embeddings_model
                or not agent_registrations
                or not self._async_qdrant_client
            ):
                logger.warning("Missing required components for indexing capabilities")
                self._vector_store_initialized.set()  # Signal that initialization is complete (with no data)
                return

            # Make sure collection is initialized
            if not self._collection_initialized:
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
            capability_to_agent_map, total_points = (
                await precompute_all_capability_embeddings(
                    self._async_qdrant_client,
                    self.COLLECTION_NAME,
                    self._embeddings_model,
                    agent_registrations,
                    self._vector_store_config.get("batch_size", 100),
                )
            )

            # Update capability map
            self._capability_to_agent_map = capability_to_agent_map

            # Signal that vector store initialization is complete
            self._vector_store_initialized.set()

        except Exception as e:
            logger.error(f"Error precomputing capability embeddings: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
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

        # Call the implementation function
        return await find_by_capability_name(
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
            return await search_with_qdrant(
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
        else:
            # Fall back to basic string similarity if Qdrant search not available
            return await fallback_string_search(
                capability_description,
                agent_registrations,
                limit,
                similarity_threshold,
                filters=filters,
            )
