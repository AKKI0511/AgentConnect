"""
Qdrant client management for capability discovery.

This module provides functions to initialize and manage Qdrant clients
for vector search operations.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.local.async_qdrant_local import AsyncQdrantLocal

# Configure logger
logger = logging.getLogger("CapabilityDiscovery.QdrantClient")

# Default collection name for agent capabilities
DEFAULT_COLLECTION_NAME = "agent_capabilities"


async def initialize_qdrant_clients(
    config: Dict[str, Any],
) -> Tuple[Optional[QdrantClient], Optional[AsyncQdrantClient]]:
    """
    Initialize both synchronous and asynchronous Qdrant clients.

    Args:
        config: Dictionary containing configuration for Qdrant clients

    Returns:
        Tuple of (sync_client, async_client) or (None, None) if initialization failed
    """
    try:
        from qdrant_client import QdrantClient, AsyncQdrantClient

        # Get Qdrant configuration
        host = config.get("host", "localhost")
        port = config.get("port", 6333)
        api_key = config.get("api_key", None)
        url = config.get("url", None)
        grpc_port = config.get("grpc_port", None)
        prefer_grpc = config.get("prefer_grpc", False)
        timeout = config.get("timeout", 30)

        # Check if in-memory mode is requested
        in_memory = config.get("in_memory", False)
        local_path = config.get("path", None)

        # Create synchronous client
        sync_client = None
        if in_memory:
            logger.info("Initializing in-memory Qdrant client")
            sync_client = QdrantClient(":memory:")
        elif local_path:
            logger.info(f"Initializing local Qdrant client at {local_path}")
            sync_client = QdrantClient(path=local_path)
        elif url:
            logger.info(f"Initializing Qdrant client with URL {url}")
            sync_client = QdrantClient(
                url=url,
                api_key=api_key,
                grpc_port=grpc_port,
                prefer_grpc=prefer_grpc,
                timeout=timeout,
            )
        else:
            logger.info(f"Initializing Qdrant client with host={host}, port={port}")
            sync_client = QdrantClient(
                host=host,
                port=port,
                api_key=api_key,
                grpc_port=grpc_port,
                prefer_grpc=prefer_grpc,
                timeout=timeout,
            )

        # Create async client with same parameters
        async_client = None
        if in_memory:
            logger.info("Initializing in-memory Async Qdrant client")
            async_client = AsyncQdrantClient(":memory:")
        elif local_path:
            logger.info(f"Initializing local Async Qdrant client at {local_path}")
            async_client = AsyncQdrantClient(path=local_path)
        elif url:
            logger.info(f"Initializing Async Qdrant client with URL {url}")
            async_client = AsyncQdrantClient(
                url=url,
                api_key=api_key,
                grpc_port=grpc_port,
                prefer_grpc=prefer_grpc,
                timeout=timeout,
            )
        else:
            logger.info(
                f"Initializing Async Qdrant client with host={host}, port={port}"
            )
            async_client = AsyncQdrantClient(
                host=host,
                port=port,
                api_key=api_key,
                grpc_port=grpc_port,
                prefer_grpc=prefer_grpc,
                timeout=timeout,
            )

        logger.info("Qdrant clients initialized successfully")
        return sync_client, async_client
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant clients: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return None, None


async def init_qdrant_collection(
    async_client: AsyncQdrantClient,
    embeddings_model: Embeddings | None = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    config: Dict[str, Any] = None,
) -> bool:
    """
    Initialize the Qdrant collection with optimized configuration.

    Args:
        async_client: Initialized AsyncQdrantClient
        embeddings_model: Initialized embeddings model
        collection_name: Name of the collection to create
        config: Dictionary containing collection configuration

    Returns:
        True if collection was initialized successfully, False otherwise
    """
    config = config or {}
    try:
        # Check if collection already exists
        collection_exists = await async_client.collection_exists(collection_name)

        # Get vector size expected by the current model
        expected_vector_size = None
        if embeddings_model:
            try:
                sample_text = "Sample text for embedding dimension detection"
                sample_embedding = embeddings_model.embed_query(sample_text)
                expected_vector_size = len(sample_embedding)
            except Exception as e:
                logger.error(
                    f"Failed to determine vector size from embedding model: {e}"
                )
                return False
        else:
            logger.error("Embeddings model not provided, cannot determine vector size.")
            return False

        if collection_exists:
            logger.info(
                f"Collection '{collection_name}' already exists. Verifying dimensions..."
            )
            try:
                collection_info = await async_client.get_collection(collection_name)
                existing_vector_size = collection_info.config.params.vectors.size

                if existing_vector_size != expected_vector_size:
                    logger.warning(
                        f"Collection '{collection_name}' exists with incorrect vector dimension "
                        f"(Existing: {existing_vector_size}, Expected: {expected_vector_size}). "
                        f"Deleting and recreating collection."
                    )
                    await async_client.delete_collection(collection_name)
                    collection_exists = False  # Force recreation
                else:
                    logger.info(
                        f"Collection '{collection_name}' dimensions verified ({existing_vector_size})."
                    )
                    return True  # Dimensions match, no need to recreate

            except Exception as e:
                logger.error(
                    f"Failed to verify existing collection dimensions: {e}. Attempting to recreate."
                )
                try:
                    await async_client.delete_collection(collection_name)
                except Exception:
                    logger.error(
                        f"Failed to delete existing collection '{collection_name}'."
                    )
                collection_exists = False  # Force recreation attempt

        # If collection doesn't exist (or was deleted due to dimension mismatch)
        if not collection_exists:
            if not expected_vector_size:
                logger.error(
                    "Cannot create collection without a valid vector size from the embedding model."
                )
                return False

            logger.info(
                f"Creating collection '{collection_name}' with vector size: {expected_vector_size}"
            )

            # Use scalar quantization if enabled in config
            quantization_config = None
            if config.get("use_quantization", True):
                from qdrant_client.http import models as qdrant_models

                # Configure scalar quantization for 4x storage reduction with minimal accuracy loss
                quantization_config = qdrant_models.ScalarQuantization(
                    scalar=qdrant_models.ScalarQuantizationConfig(
                        # Type can be int8 (default) for 4x compression or float16 for 2x compression
                        type=qdrant_models.ScalarType.INT8,
                        # Whether to quantize vectors during building of HNSW index
                        quantile=0.99,  # Trim outliers for better quantization
                        always_ram=True,  # Keep quantized vectors in RAM for faster search
                    )
                )

            # Configure vector params with optimized HNSW index
            from qdrant_client.http import models as qdrant_models

            # Create HNSW config as a dictionary instead of an object
            # This is the expected format according to Qdrant docs
            hnsw_config = qdrant_models.HnswConfigDiff(
                m=16,  # Number of bidirectional links created for each new element (default: 16)
                ef_construct=100,  # Controls index build time vs quality (higher=better quality, slower build)
                full_scan_threshold=10000,  # Threshold for using brute force search instead of HNSW
                max_indexing_threads=4,  # Number of threads to use for indexing
                on_disk=config.get(
                    "index_on_disk", False
                ),  # Whether to store index on disk
            )

            vector_config = qdrant_models.VectorParams(
                size=expected_vector_size,
                distance=qdrant_models.Distance.COSINE,
                on_disk=config.get("vectors_on_disk", False),
                # Pass HNSW config as HnswConfigDiff object
                hnsw_config=hnsw_config,
                # Add quantization if enabled
                quantization_config=quantization_config,
            )

            try:
                # Create the collection with optimized configuration
                await async_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=vector_config,
                    # Create payload indexes for efficient filtering
                    optimizers_config=qdrant_models.OptimizersConfigDiff(
                        deleted_threshold=0.2,  # Required field - cleanup segments when 20% of vectors are deleted
                        vacuum_min_vector_number=1000,  # Minimal number of vectors for vacuum optimization
                        default_segment_number=2,  # Default number of segments, better for multi-core systems
                        memmap_threshold=20000,  # Use memory mapping for collections with > 20k points
                        indexing_threshold=20000,  # Index when segment has more than 20k vectors
                        flush_interval_sec=5,  # Required field - flush interval in seconds
                    ),
                    timeout=60,  # Give enough time for collection creation
                )

                logger.info(f"Created collection {collection_name}")

                # Verify collection was created
                collection_exists = await async_client.collection_exists(
                    collection_name
                )
                if not collection_exists:
                    logger.error(f"Failed to create collection {collection_name}")
                    return False

            except Exception as e:
                logger.error(f"Error creating collection: {str(e)}")
                return False

            # Create payload indexes for the fields we'll filter on
            try:
                # Check if this is an in-memory client - payload indexes don't work with local/in-memory Qdrant
                if isinstance(async_client._client, AsyncQdrantLocal):
                    logger.info(
                        "Skipping payload indexes for in-memory/local Qdrant instance"
                    )
                else:
                    # Only create payload indexes for remote Qdrant instances
                    payload_indexes = [
                        "agent_id",
                        "agent_type",
                        "organization",
                        "developer",
                        "tags",
                    ]

                    for field in payload_indexes:
                        try:
                            await async_client.create_payload_index(
                                collection_name=collection_name,
                                field_name=field,
                                field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
                                wait=True,
                            )
                            logger.info(f"Created payload index for field {field}")
                        except Exception as field_error:
                            logger.warning(
                                f"Failed to create payload index for {field}: {str(field_error)}"
                            )
                            # Continue with other fields even if one fails
                            continue

            except Exception as index_error:
                logger.warning(
                    f"Failed to create some payload indexes: {str(index_error)}"
                )
                # Continue even if payload indexes fail - they're not critical
                # The collection is still usable without them, just less efficient

            logger.info(
                f"Successfully created collection {collection_name} with optimized configuration"
            )
            return True

    except Exception as e:
        logger.error(f"Failed to initialize Qdrant collection: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False


async def delete_points_by_agent_id(
    async_client: AsyncQdrantClient, collection_name: str, agent_id: str
) -> List[str]:
    """
    Delete all points associated with a specific agent ID from a Qdrant collection.

    Args:
        async_client: Initialized AsyncQdrantClient
        collection_name: Name of the collection to delete from
        agent_id: ID of the agent to delete

    Returns:
        List of deleted point IDs
    """

    try:
        from qdrant_client.http import models as qdrant_models

        # Create filter for all points related to this agent
        agent_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="agent_id", match=qdrant_models.MatchValue(value=agent_id)
                )
            ]
        )

        # Get the IDs of points to delete
        search_result = await async_client.scroll(
            collection_name=collection_name,
            scroll_filter=agent_filter,  # Use scroll_filter instead of filter
            limit=1000,  # Get up to 1000 points
            with_vectors=False,  # Don't need vectors, just IDs
            with_payload=False,  # Don't need payloads, just IDs
        )

        points = search_result[0]  # First element is the list of points

        if not points:
            logger.debug(f"No points found for agent: {agent_id}")
            return []

        # Extract the IDs
        point_ids = [str(point.id) for point in points]

        # Delete the points from Qdrant
        await async_client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.PointIdsList(points=point_ids),
        )

        logger.info(f"Deleted {len(point_ids)} points for agent: {agent_id}")
        return point_ids

    except Exception as e:
        logger.error(f"Error deleting points for agent {agent_id}: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return []
