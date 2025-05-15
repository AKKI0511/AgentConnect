"""
Search functionality for capability discovery.

This module provides functions for searching agents by capability, using
both string-matching and semantic (vector) search approaches.
"""

import logging
from typing import Callable, Dict, List, Set, Tuple, Optional, Awaitable
from langchain_core.embeddings import Embeddings
from qdrant_client import AsyncQdrantClient

from agentconnect.core.registry.registration import AgentRegistration

# Configure logger
logger = logging.getLogger("CapabilityDiscovery.Search")

# Local imports
from agentconnect.core.registry.capability_discovery_impl.embedding_utils import (
    calculate_similarity,
)


async def find_by_capability_name(
    capability_name: str,
    agent_registrations: Dict[str, AgentRegistration],
    capabilities_index: Dict[str, Set[str]],
    qdrant_search_func: Optional[
        Callable[
            [
                str,
                Dict[str, AgentRegistration],
                int,
                float,
                Optional[Dict[str, List[str]]],
            ],
            Awaitable[List[Tuple[AgentRegistration, float]]],
        ]
    ] = None,
    limit: int = 10,
    similarity_threshold: float = 0.1,
) -> List[AgentRegistration]:
    """
    Find agents by capability name (simple string matching).

    Args:
        capability_name: Name of the capability to search for
        agent_registrations: Dictionary of agent registrations
        capabilities_index: Index of agent capabilities
        qdrant_search_func: Function to use for semantic search fallback
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
    if not matching_registrations and qdrant_search_func:
        try:
            # If we have Qdrant initialized, do semantic search instead
            semantic_results = await qdrant_search_func(
                capability_name, agent_registrations, limit, similarity_threshold
            )

            # Return all results from semantic search without filtering
            if semantic_results:
                logger.debug(
                    f"No exact matches for '{capability_name}', returning {len(semantic_results)} semantic matches"
                )
                return [registration for registration, _ in semantic_results][:limit]
        except Exception as e:
            logger.warning(f"Error in semantic fallback search: {str(e)}")
            import traceback

            logger.warning(traceback.format_exc())

    return matching_registrations[:limit]


async def search_with_qdrant(
    async_client: AsyncQdrantClient,
    collection_name: str,
    capability_description: str,
    embeddings_model: Embeddings,
    agent_registrations: Dict[str, AgentRegistration],
    capability_to_agent_map: Dict[str, AgentRegistration],
    limit: int = 10,
    similarity_threshold: float = 0.1,
    filters: Optional[Dict[str, List[str]]] = None,
) -> List[Tuple[AgentRegistration, float]]:
    """
    Find agents by capability description using Qdrant hybrid search with metadata filtering.

    Args:
        async_client: Initialized AsyncQdrantClient
        collection_name: Name of the collection to search
        capability_description: Description of the capability to search for
        embeddings_model: Initialized embeddings model
        agent_registrations: Dictionary of agent registrations
        capability_to_agent_map: Dictionary mapping doc_ids to agent registrations
        limit: Maximum number of results to return (default: 10)
        similarity_threshold: Minimum similarity score to include in results (default: 0.1)
        filters: Optional dictionary for filtering. Keys can include "tags",
                 "organization", "developer", "default_input_modes", "default_output_modes", "auth_schemes".
                 Values are lists of strings to match for the respective key.

    Returns:
        List of tuples containing agent registrations and similarity scores
    """
    logger.debug(
        f"Searching agents with capability description: {capability_description}, "
        f"limit: {limit}, threshold: {similarity_threshold}, filters: {filters}"
    )

    try:
        # Generate embedding for the search query
        query_embedding = embeddings_model.embed_query(capability_description)

        # Build filter conditions based on the provided filters dictionary.
        # Note: These Qdrant filters perform *exact* matches on metadata fields.
        # Semantic relevance between the overall query (capability_description)
        # and agent content is handled by the vector similarity search itself.
        filter_conditions = []
        if filters:
            from qdrant_client.http import models as qdrant_models

            for key, values in filters.items():
                if not values:  # Skip if no values are provided for a filter key
                    continue

                if key == "tags":
                    filter_conditions.append(
                        qdrant_models.FieldCondition(
                            key="tags",  # 'tags' field is consistently named across point types
                            match=qdrant_models.MatchAny(any=values),
                        )
                    )
                elif key in ["organization", "developer"]:
                    # These fields generally exist on 'agent_profile' points.
                    # The filter will apply if the matched point is a profile.
                    # Assumes values[0] is the string to match for these single-value fields.
                    filter_conditions.append(
                        qdrant_models.FieldCondition(
                            key=key, match=qdrant_models.MatchValue(value=values[0])
                        )
                    )
                elif key in [
                    "default_input_modes",
                    "default_output_modes",
                    "auth_schemes",
                ]:
                    # These logical filters map to different fields depending on point type:
                    # - key (e.g., "default_input_modes") for profile points
                    # - "agent_" + key (e.g., "agent_default_input_modes") for capability/skill points

                    agent_prefixed_key = f"agent_{key}"

                    # Create a nested filter with a 'should' condition to match either field name.
                    # This entire Filter object (containing the 'should') becomes one condition in the 'must' list.
                    should_filter_for_key = qdrant_models.Filter(
                        should=[
                            qdrant_models.FieldCondition(
                                key=key,  # e.g., "default_input_modes"
                                match=qdrant_models.MatchAny(any=values),
                            ),
                            qdrant_models.FieldCondition(
                                key=agent_prefixed_key,  # e.g., "agent_default_input_modes"
                                match=qdrant_models.MatchAny(any=values),
                            ),
                        ]
                    )
                    filter_conditions.append(should_filter_for_key)
                else:
                    logger.warning(
                        f"Encountered an unknown filter key: {key}. This filter will be ignored."
                    )
                # Add other filterable fields here if necessary, following the pattern above.

        # Create the filter if we have any conditions
        query_filter = None
        if filter_conditions:
            query_filter = qdrant_models.Filter(must=filter_conditions)

        # Perform the vector search against Qdrant using query_points instead of search
        search_result = await async_client.query_points(
            collection_name=collection_name,
            query=query_embedding,
            query_filter=query_filter,
            limit=limit * 3,  # Request more results to allow for deduplication
            score_threshold=similarity_threshold,  # range -1 to 1 (theoretically) in practice <= 0 is irrelevant
            with_payload=True,  # Include metadata
        )

        # Track seen agent IDs to avoid duplicates
        seen_agent_ids = set()
        processed_results = []

        for scored_point in search_result.points:
            # Get agent_id from payload
            agent_id = scored_point.payload.get("agent_id")

            # Skip duplicate agents - we want one result per agent
            if agent_id in seen_agent_ids:
                continue

            # Get the registration from our map or from the provided agent_registrations
            doc_id = scored_point.payload.get("doc_id")
            registration = None

            if doc_id in capability_to_agent_map:
                registration = capability_to_agent_map[doc_id]
            elif agent_id in agent_registrations:
                registration = agent_registrations[agent_id]
            else:
                # Skip if we don't have registration info
                logger.debug(f"No registration found for agent {agent_id}")
                continue

            # Log the raw Qdrant score
            logger.debug(
                f"Qdrant search result for '{capability_description}': "
                f"Agent={agent_id}, "
                f"Doc_id={doc_id}, "
                f"Score={scored_point.score:.3f}"
            )

            # Append result with raw score. Filtering is handled by Qdrant's score_threshold.
            processed_results.append((registration, scored_point.score))
            seen_agent_ids.add(agent_id)

        # Sort by raw score (highest first)
        processed_results.sort(key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Qdrant search returned {len(processed_results)} matching agents after initial query"
        )
        # Limit results after potential deduplication
        return processed_results[:limit]

    except Exception as e:
        logger.warning(
            f"Error using Qdrant search: {str(e)}. Falling back to simple similarity."
        )
        import traceback

        logger.warning(traceback.format_exc())

        # Fall back to basic string similarity if Qdrant search fails
        return await fallback_string_search(
            capability_description,
            agent_registrations,
            limit,
            similarity_threshold,
            filters,
        )


async def fallback_string_search(
    capability_description: str,
    agent_registrations: Dict[str, AgentRegistration],
    limit: int = 10,
    similarity_threshold: float = 0.1,
    filters: Optional[Dict[str, List[str]]] = None,
) -> List[Tuple[AgentRegistration, float]]:
    """
    Fallback search method using simple string similarity.

    Args:
        capability_description: Description of the capability to search for
        agent_registrations: Dictionary of agent registrations
        limit: Maximum number of results to return (default: 10)
        similarity_threshold: Minimum similarity score to include in results (default: 0.1)
        filters: Optional dictionary for filtering. Keys can include "tags",
                 "organization", "developer", "default_input_modes", "default_output_modes", "auth_schemes".

    Returns:
        List of tuples containing agent registrations and similarity scores
    """
    logger.debug(
        f"Using fallback string similarity search with Jaccard similarity. Filters: {filters}"
    )
    logger.debug(
        "Note: Fallback search uses similarity metrics (higher scores are better)"
    )

    results = []

    # Apply filters first
    filtered_registrations = {}
    for agent_id, registration in agent_registrations.items():
        passes_filters = True
        if filters:
            for key, required_values in filters.items():
                if not required_values:
                    continue

                reg_value = getattr(registration, key, None)

                if key in [
                    "tags",
                    "default_input_modes",
                    "default_output_modes",
                    "auth_schemes",
                ]:
                    if not isinstance(reg_value, list) or not any(
                        val in reg_value for val in required_values
                    ):
                        passes_filters = False
                        break
                elif key in ["organization", "developer"]:
                    if (
                        reg_value not in required_values
                    ):  # Assumes single value fields from registration
                        passes_filters = False
                        break

        if passes_filters:
            filtered_registrations[agent_id] = registration

    # Now apply similarity search on filtered registrations
    for agent_id, registration in filtered_registrations.items():
        # For profile text
        profile_parts = [
            registration.name or "",
            registration.summary or "",
            registration.description or "",
            # Include other profile fields that might be relevant
            ", ".join([cap.name for cap in registration.capabilities]),
            (
                ", ".join([skill.name for skill in registration.skills])
                if hasattr(registration, "skills")
                else ""
            ),
            ", ".join(registration.tags) if registration.tags else "",
        ]
        profile_text = " ".join(filter(None, profile_parts))

        profile_similarity = calculate_similarity(capability_description, profile_text)

        # Also check individual capabilities for backward compatibility
        capability_similarity = 0.0
        for capability in registration.capabilities:
            capability_text = f"{capability.name} {capability.description}"
            similarity = calculate_similarity(capability_description, capability_text)
            capability_similarity = max(capability_similarity, similarity)

        # Use the higher of the two similarities
        highest_similarity = max(profile_similarity, capability_similarity)

        # Only include results above the threshold
        if highest_similarity >= similarity_threshold:
            logger.debug(
                f"Fallback search result for '{capability_description}': Agent={agent_id}, "
                f"Score={highest_similarity:.3f} (above threshold {similarity_threshold})"
            )
            results.append((registration, highest_similarity))
        else:
            logger.debug(
                f"Skipping agent {agent_id} with similarity {highest_similarity:.3f} - below threshold {similarity_threshold}"
            )

    # Sort by similarity score (highest first for fallback similarity metrics)
    results.sort(key=lambda x: x[1], reverse=True)
    logger.debug(
        f"Fallback string similarity search found {len(results)} matching agents after filtering"
    )
    return results[:limit]  # Limit the results to the specified limit
