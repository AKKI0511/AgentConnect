"""
Capability discovery functionality for the AgentConnect framework.

This module provides functions for searching and discovering agent capabilities,
including semantic search using embeddings and simpler string matching methods.
It leverages LangChain's vector stores for efficient semantic search.
"""

# Standard library imports
import logging
import asyncio
import warnings
from typing import Dict, List, Set, Tuple, Any, Optional
from langchain_core.vectorstores import VectorStore
from langchain_huggingface import HuggingFaceEmbeddings

# Absolute imports from agentconnect package
from agentconnect.core.registry.registration import AgentRegistration

# Set up logging
logger = logging.getLogger("CapabilityDiscovery")

# Permanently filter out UserWarnings about relevance scores from any source
warnings.filterwarnings(
    "ignore", message="Relevance scores must be between 0 and 1", category=UserWarning
)
warnings.filterwarnings("ignore", message=".*elevance scores.*", category=UserWarning)

# Monkeypatch the showwarning function to completely suppress relevance score warnings
original_showwarning = warnings.showwarning


def custom_showwarning(message, category, filename, lineno, file=None, line=None):
    """
    Custom warning handler to suppress relevance score warnings.

    Args:
        message: The warning message
        category: The warning category
    """
    if category == UserWarning and "relevance scores" in str(message).lower():
        return  # Suppress the warning completely
    # For all other warnings, use the original function
    return original_showwarning(message, category, filename, lineno, file, line)


warnings.showwarning = custom_showwarning


def check_semantic_search_requirements() -> Dict[str, bool]:
    """
    Check if the required packages for semantic search are installed.

    Returns:
        Dictionary indicating which vector store backends are available
    """
    available_backends = {
        "faiss": False,
        "usearch": False,
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

    # Check for FAISS backend
    try:
        # Import inside function to prevent lint errors
        from langchain_community.vectorstores import FAISS  # noqa: F401

        available_backends["faiss"] = True
    except ImportError as e:
        logger.warning(f"FAISS vector store not available: {str(e)}")
        logger.warning(
            "To enable FAISS vector search, install: pip install langchain-community faiss-cpu"
        )

    # Check for USearch backend (lighter alternative)
    try:
        # Import inside function to prevent lint errors
        from langchain_community.vectorstores import USearch  # noqa: F401

        available_backends["usearch"] = True
    except ImportError as e:
        logger.warning(f"USearch vector store not available: {str(e)}")
        logger.warning(
            "To enable USearch vector search, install: pip install langchain-community usearch"
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
    import numpy as np

    dot_product = np.dot(vec1, vec2)
    norm_a = np.linalg.norm(vec1)
    norm_b = np.linalg.norm(vec2)

    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class CapabilityDiscoveryService:
    """
    Service for discovering agent capabilities through various search methods.

    This class provides methods for finding agents based on their capabilities,
    including exact string matching and semantic search using vector stores.
    """

    def __init__(self, vector_store_config: Dict[str, Any] = None):
        """
        Initialize the capability discovery service.

        Args:
            vector_store_config: Optional configuration for vector store
                                 Can include 'prefer_backend', 'model_name', etc.
        """
        self._embeddings_model = None
        self._vector_store: Optional[VectorStore] = None
        self._capability_to_agent_map: Dict[str, AgentRegistration] = (
            {}
        )  # Maps document IDs to capability/agent data
        self._vector_store_config = vector_store_config or {}
        self._available_backends = {}
        self._vector_store_initialized = asyncio.Event()
        self._vector_store_initialized.clear()

    async def initialize_embeddings_model(self):
        """
        Initialize the embeddings model for semantic search.

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

            if not (
                self._available_backends["faiss"] or self._available_backends["usearch"]
            ):
                logger.warning(
                    "No vector store backend available, semantic search will fall back to basic similarity"
                )
                return

            # Get model name from config or use default
            model_name = self._vector_store_config.get(
                "model_name", "sentence-transformers/all-mpnet-base-v2"
            )

            logger.info(
                f"Initializing embeddings model {model_name} for semantic search..."
            )

            # Create embeddings model with caching
            cache_folder = self._vector_store_config.get(
                "cache_folder", "./.cache/huggingface/embeddings"
            )

            # Try with explicit model_kwargs and encode_kwargs first
            try:
                self._embeddings_model = HuggingFaceEmbeddings(
                    model_name=model_name,
                    cache_folder=cache_folder,
                    model_kwargs={"device": "cpu", "revision": "main"},
                    encode_kwargs={"normalize_embeddings": True},
                )
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
                    self._embeddings_model = HuggingFaceEmbeddings(
                        model=st_model, encode_kwargs={"normalize_embeddings": True}
                    )

                    logger.info(
                        "Initialized embeddings using pre-loaded sentence transformer model"
                    )
                except Exception as fallback_error:
                    # If that fails too, try with minimal parameters
                    logger.warning(
                        f"Fallback embedding initialization failed: {str(fallback_error)}"
                    )

                    # Last attempt with minimal configuration
                    self._embeddings_model = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",  # Try with a smaller model
                    )

                    logger.info(
                        "Initialized embeddings with minimal configuration and smaller model"
                    )

            # Reset capability map
            self._capability_to_agent_map = {}

            # Vector store will be initialized in precompute_all_capability_embeddings
            self._vector_store = None

            logger.info("Embeddings model initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize embeddings model: {str(e)}")
            import traceback

            logger.warning(traceback.format_exc())

    async def _init_vector_store(
        self, documents: List, embeddings_model: "HuggingFaceEmbeddings"
    ) -> Any:
        """
        Initialize vector store with the preferred backend.

        Args:
            documents: List of documents to index
            embeddings_model: Embedding model to use

        Returns:
            Initialized vector store or None if initialization failed
        """
        # Determine which backend to use
        preferred_backend = self._vector_store_config.get("prefer_backend", "faiss")

        # Vector store parameters
        # Some vector stores support normalization through kwargs
        common_kwargs = {
            # Set normalization parameters if supported - these may be ignored by backends that don't support them
            "normalize_embeddings": True,  # Normalize embeddings for better cosine similarity
            "relevance_score_fn": "max_inner_product",  # Use max inner product for relevance scoring
        }

        # Try preferred backend first
        if preferred_backend == "usearch" and self._available_backends["usearch"]:
            try:
                from langchain_community.vectorstores import USearch

                # Initialize USearch
                logger.info("Initializing USearch vector store...")
                vector_store = USearch.from_documents(
                    documents,
                    embeddings_model,
                    **{
                        k: v
                        for k, v in common_kwargs.items()
                        if k in USearch.from_documents.__code__.co_varnames
                    },
                )
                logger.info("USearch vector store initialized successfully")
                return vector_store
            except Exception as e:
                logger.warning(f"Failed to initialize USearch vector store: {str(e)}")

        # Try FAISS if USearch fails or is not preferred
        if self._available_backends["faiss"]:
            try:
                from langchain_community.vectorstores import FAISS

                # Initialize FAISS asynchronously if possible
                logger.info("Initializing FAISS vector store...")

                # Filter kwargs to only include those supported by FAISS
                faiss_kwargs = {
                    k: v
                    for k, v in common_kwargs.items()
                    if k in FAISS.afrom_documents.__code__.co_varnames
                }

                vector_store = await FAISS.afrom_documents(
                    documents, embeddings_model, **faiss_kwargs
                )
                logger.info("FAISS vector store initialized successfully")
                return vector_store
            except Exception as e:
                logger.warning(f"Failed to initialize FAISS vector store: {str(e)}")

                # Try synchronous initialization as fallback
                try:
                    from langchain_community.vectorstores import FAISS

                    # Filter kwargs to only include those supported by FAISS
                    faiss_kwargs = {
                        k: v
                        for k, v in common_kwargs.items()
                        if k in FAISS.from_documents.__code__.co_varnames
                    }

                    vector_store = FAISS.from_documents(
                        documents, embeddings_model, **faiss_kwargs
                    )
                    logger.info(
                        "FAISS vector store initialized successfully (sync fallback)"
                    )
                    return vector_store
                except Exception as e:
                    logger.warning(
                        f"Failed to initialize FAISS vector store (sync fallback): {str(e)}"
                    )

        # If all else fails
        logger.error("Failed to initialize any vector store")
        return None

    async def update_capability_embeddings_cache(
        self, registration: AgentRegistration
    ) -> None:
        """
        Update capability embeddings for a registration.

        Args:
            registration: Registration information for the agent
        """
        try:
            # Skip if no capabilities or embeddings model not initialized
            if not registration.capabilities or not self._embeddings_model:
                return

            # For simplicity, we'll just rebuild the entire index
            # In a production environment, you would want to implement incremental updates
            # Get all registrations including the updated one
            all_registrations = {}

            # Add all existing registrations
            for doc_id, reg in self._capability_to_agent_map.items():
                agent_id = doc_id.split(":", 1)[0]
                all_registrations[agent_id] = reg

            # Add the updated registration
            all_registrations[registration.agent_id] = registration

            # Rebuild the index
            await self.precompute_all_capability_embeddings(all_registrations)

            logger.debug(
                f"Updated capability embeddings for agent: {registration.agent_id}"
            )
        except Exception as e:
            logger.warning(f"Error updating capability embeddings: {str(e)}")
            import traceback

            logger.warning(traceback.format_exc())

    def clear_agent_embeddings_cache(self, agent_id: str) -> None:
        """
        Clear the embeddings cache for a specific agent.

        Args:
            agent_id: ID of the agent to clear cache for
        """
        # Remove agent from capability_to_agent_map
        doc_ids_to_remove = [
            doc_id
            for doc_id in self._capability_to_agent_map.keys()
            if doc_id.startswith(f"{agent_id}:")
        ]

        for doc_id in doc_ids_to_remove:
            del self._capability_to_agent_map[doc_id]

        # Rebuild the index if we have remaining registrations
        if self._capability_to_agent_map and self._vector_store:
            try:
                # Get all remaining registrations
                all_registrations = {}
                for doc_id, reg in self._capability_to_agent_map.items():
                    agent_id = doc_id.split(":", 1)[0]
                    all_registrations[agent_id] = reg

                # Use asyncio.create_task to rebuild in the background
                import asyncio

                asyncio.create_task(
                    self.precompute_all_capability_embeddings(all_registrations)
                )

                logger.debug(
                    f"Scheduled index rebuild after removing agent: {agent_id}"
                )
            except Exception as e:
                logger.warning(f"Error scheduling index rebuild: {str(e)}")

        logger.debug(f"Cleared embeddings for agent: {agent_id}")

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
            from langchain_core.documents import Document

            # Process all capabilities to create documents for the vector store
            documents = []
            self._capability_to_agent_map = {}

            for agent_id, registration in agent_registrations.items():
                for capability in registration.capabilities:
                    # Create a rich text representation that includes both name and description
                    capability_text = f"{capability.name} {capability.description}"

                    # Create a unique ID for this capability
                    doc_id = f"{agent_id}:{capability.name}"

                    # Create a Document object with rich metadata
                    doc = Document(
                        page_content=capability_text,
                        metadata={
                            "agent_id": agent_id,
                            "capability_name": capability.name,
                            "capability_description": capability.description,
                            "doc_id": doc_id,
                            "agent_type": str(registration.agent_type),
                            "agent_display_name": registration.metadata.get(
                                "name", agent_id
                            ),
                        },
                    )
                    documents.append(doc)

                    # Store a reference to the registration for later use
                    self._capability_to_agent_map[doc_id] = registration

            if not documents:
                logger.info("No capabilities found to index")
                self._vector_store_initialized.set()  # Signal that initialization is complete (with no data)
                return

            # Initialize vector store with the appropriate backend
            self._vector_store = await self._init_vector_store(
                documents, self._embeddings_model
            )

            if self._vector_store:
                logger.info(
                    f"Precomputed embeddings for {len(documents)} capabilities using vector store"
                )
            else:
                logger.warning(
                    "Failed to initialize vector store, semantic search will be limited"
                )

            # Signal that vector store initialization is complete
            self._vector_store_initialized.set()

        except Exception as e:
            logger.warning(f"Error precomputing capability embeddings: {str(e)}")
            import traceback

            logger.warning(traceback.format_exc())
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
        logger.debug(
            f"Searching agents with capability: {capability_name}, limit: {limit}, threshold: {similarity_threshold}"
        )
        agent_ids = capabilities_index.get(capability_name, set())
        matching_registrations = [
            agent_registrations[agent_id]
            for agent_id in agent_ids
            if agent_id in agent_registrations
        ]

        # If no exact matches, try semantic search fallback if available
        if not matching_registrations and self._vector_store:
            try:
                # Wait for vector store to be initialized (with timeout)
                await asyncio.wait_for(
                    self._vector_store_initialized.wait(), timeout=10.0
                )

                # If we have vector store, do semantic search instead
                semantic_results = await self.find_by_capability_semantic(
                    capability_name, agent_registrations, limit, similarity_threshold
                )

                # Return all results from semantic search without filtering
                if semantic_results:
                    logger.debug(
                        f"No exact matches for '{capability_name}', returning {len(semantic_results)} semantic matches"
                    )
                    return [registration for registration, _ in semantic_results][
                        :limit
                    ]
            except Exception as e:
                logger.warning(f"Error in semantic fallback search: {str(e)}")

        return matching_registrations[:limit]

    async def find_by_capability_semantic(
        self,
        capability_description: str,
        agent_registrations: Dict[str, AgentRegistration],
        limit: int = 10,
        similarity_threshold: float = 0.1,
    ) -> List[Tuple[AgentRegistration, float]]:
        """
        Find agents by capability description using semantic search.

        Args:
            capability_description: Description of the capability to search for
            agent_registrations: Dictionary of agent registrations
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score to include in results (default: 0.1)
                                  For negative scores (distance metrics), this becomes a maximum threshold
                                  (lower absolute value means more similar)

        Returns:
            List of tuples containing agent registrations and similarity scores
        """
        logger.debug(
            f"Searching agents with capability description: {capability_description}, limit: {limit}, threshold: {similarity_threshold}"
        )
        results = []

        # Make sure vector store is initialized if possible
        if self._vector_store is None and self._embeddings_model:
            # Wait for vector store to be initialized (with timeout)
            try:
                await asyncio.wait_for(
                    self._vector_store_initialized.wait(), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for vector store initialization")
            except Exception as e:
                logger.warning(
                    f"Error waiting for vector store initialization: {str(e)}"
                )

        logger.debug(
            f"Starting semantic search for capability: '{capability_description}'"
        )

        # Check if we can use vector search
        if (
            self._embeddings_model
            and self._vector_store
            and self._capability_to_agent_map
        ):
            try:
                # Completely disable all warnings during search call - no matter what, don't show warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # Try using async similarity search with scores
                    try:
                        kwargs = {}
                        search_results = await self._vector_store.asimilarity_search_with_relevance_scores(
                            capability_description, k=limit * 2, **kwargs
                        )
                    except (AttributeError, NotImplementedError):
                        # Fall back to sync search if async not supported
                        kwargs = {}
                        search_results = (
                            self._vector_store.similarity_search_with_relevance_scores(
                                capability_description, k=limit * 2, **kwargs
                            )
                        )

                # Handle any potential issues with the search results format
                cleaned_search_results = []
                for item in search_results:
                    # Make sure each result is a proper tuple of (doc, score)
                    if not isinstance(item, tuple) or len(item) != 2:
                        logger.warning(f"Skipping malformed search result: {item}")
                        continue

                    doc, score = item
                    # Convert score to float if necessary
                    if hasattr(score, "item"):  # Convert numpy types
                        score = float(score.item())
                    elif not isinstance(score, (int, float)):
                        try:
                            score = float(score)
                        except (ValueError, TypeError):
                            logger.warning(f"Could not convert score to float: {score}")
                            continue

                    cleaned_search_results.append((doc, score))

                # Process results
                seen_agent_ids = set()
                processed_results = []

                for doc, original_score in cleaned_search_results:
                    # --- Filter 1: Exclude non-positive cosine scores ---
                    # Scores <= 0 indicate orthogonality or dissimilarity in cosine similarity.
                    if original_score <= 0:
                        logger.debug(
                            f"Skipping result: Original cosine score {original_score:.3f} is not positive (indicates dissimilarity)."
                        )
                        continue  # Skip this result entirely

                    # --- Score Normalization (only for positive scores) ---
                    # Assuming scores are now in (0, 1] range based on the filter above.
                    # Normalize cosine similarity S from (0, 1] to (0.5, 1] using (S+1)/2
                    # This maintains relative order and maps to a 0-1 range suitable for the threshold.
                    normalized_score = (original_score + 1.0) / 2.0
                    score_type = "cosine_similarity"  # Confirmed by filtering

                    # --- Filter 2: Apply similarity threshold to normalized score ---
                    if normalized_score < similarity_threshold:
                        logger.debug(
                            f"Skipping result: Normalized score {normalized_score:.3f} "
                            f"(original {score_type}: {original_score:.3f}) is below threshold {similarity_threshold}"
                        )
                        continue

                    # --- Process valid results that passed both filters ---
                    doc_id = doc.metadata.get("doc_id")
                    if doc_id in self._capability_to_agent_map:
                        registration = self._capability_to_agent_map[doc_id]

                        # Only include each agent once
                        if registration.agent_id not in seen_agent_ids:
                            logger.debug(
                                f"Vector search result for '{capability_description}': Agent={registration.agent_id}, "
                                f"Cap={doc.metadata.get('capability_name', 'unknown')}, "
                                f"Original score ({score_type})={original_score:.3f}, Normalized score={normalized_score:.3f}"
                            )
                            # Store registration, original score, and normalized score for sorting
                            processed_results.append(
                                (registration, original_score, normalized_score)
                            )
                            seen_agent_ids.add(registration.agent_id)

                # Sort by normalized score (higher is better, 0-1 range derived from (0.5, 1])
                processed_results.sort(key=lambda x: x[2], reverse=True)

                # Create final results list containing registration and the *original* score
                results = [
                    (reg, orig_score)
                    for reg, orig_score, norm_score in processed_results
                ]

                logger.debug(
                    f"Vector store search found {len(results)} matching agents after filtering by normalized threshold {similarity_threshold}"
                )
                return results[:limit]  # Limit the results

            except Exception as e:
                logger.warning(
                    f"Error using vector store search: {str(e)}. Falling back to simple similarity."
                )
                import traceback

                logger.warning(traceback.format_exc())

        # Fallback to simple string similarity
        logger.debug("Using fallback string similarity search with Jaccard similarity")
        logger.debug(
            "Note: Fallback search uses similarity metrics (higher scores are better)"
        )
        for agent_id, registration in agent_registrations.items():
            highest_similarity = 0.0
            highest_match = None

            for capability in registration.capabilities:
                # Simple string similarity check (Jaccard similarity)
                capability_text = f"{capability.name} {capability.description}"

                # Calculate simple Jaccard similarity
                words1 = set(capability_description.lower().split())
                words2 = set(capability_text.lower().split())

                if not words1 or not words2:
                    continue

                intersection = words1.intersection(words2)
                union = words1.union(words2)
                similarity = len(intersection) / len(union)

                if similarity > highest_similarity:
                    highest_similarity = similarity
                    highest_match = capability.name

            # Only include results above the threshold - for fallback, higher is always better
            if highest_similarity >= similarity_threshold:
                # Include all results with their raw similarity score
                logger.debug(
                    f"Fallback search result for '{capability_description}': Agent={agent_id}, "
                    f"Best match={highest_match}, Score={highest_similarity:.3f} (above threshold {similarity_threshold})"
                )
                results.append((registration, highest_similarity))
            else:
                logger.debug(
                    f"Skipping agent {agent_id} with similarity {highest_similarity:.3f} - below threshold {similarity_threshold}"
                )

        # Sort by similarity score (highest first for fallback similarity metrics)
        results.sort(key=lambda x: x[1], reverse=True)
        logger.debug(
            f"Fallback string similarity search found {len(results)} matching agents after filtering by threshold {similarity_threshold}"
        )
        return results[:limit]  # Limit the results to the specified limit

    async def save_vector_store(self, path: str) -> bool:
        """
        Save the vector store to disk for faster loading in the future.

        Args:
            path: Directory path to save the vector store

        Returns:
            True if successful, False otherwise
        """
        if not self._vector_store:
            logger.warning("No vector store to save")
            return False

        try:
            # Wait for vector store to be initialized
            await asyncio.wait_for(self._vector_store_initialized.wait(), timeout=10.0)

            # Check if the save method is implemented
            if hasattr(self._vector_store, "save_local"):
                self._vector_store.save_local(path)
                logger.info(f"Vector store saved to {path}")
                return True
            else:
                logger.warning("Vector store does not support saving to disk")
                return False
        except Exception as e:
            logger.error(f"Error saving vector store: {str(e)}")
            return False

    async def load_vector_store(self, path: str, embeddings_model=None) -> bool:
        """
        Load the vector store from disk.

        Args:
            path: Directory path to load the vector store from
            embeddings_model: Optional embeddings model to use (if None, uses the current one)

        Returns:
            True if successful, False otherwise
        """
        if not embeddings_model and not self._embeddings_model:
            logger.warning("No embeddings model available for loading vector store")
            return False

        embeddings = embeddings_model or self._embeddings_model

        try:
            # Try FAISS first
            if self._available_backends["faiss"]:
                try:
                    from langchain_community.vectorstores import FAISS

                    self._vector_store = FAISS.load_local(
                        path,
                        embeddings,
                        allow_dangerous_deserialization=True,  # Allow deserialization for testing
                    )
                    logger.info(f"Loaded FAISS vector store from {path}")
                    self._vector_store_initialized.set()
                    return True
                except Exception as e:
                    logger.warning(f"Error loading FAISS vector store: {str(e)}")

            # Try USearch if FAISS fails
            if self._available_backends["usearch"]:
                try:
                    from langchain_community.vectorstores import USearch

                    self._vector_store = USearch.load_local(path, embeddings)
                    logger.info(f"Loaded USearch vector store from {path}")
                    self._vector_store_initialized.set()
                    return True
                except Exception as e:
                    logger.warning(f"Error loading USearch vector store: {str(e)}")

            logger.warning("Failed to load vector store from disk")
            return False
        except Exception as e:
            logger.error(f"Error loading vector store: {str(e)}")
            return False
