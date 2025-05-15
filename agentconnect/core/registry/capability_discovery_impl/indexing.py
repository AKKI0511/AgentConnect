"""
Indexing functionality for capability discovery.

This module provides functions for indexing agent capabilities into Qdrant,
handling updates, deletions, and processing agent registrations.
"""

import logging
from typing import Dict, Set, Tuple, List
from langchain_core.embeddings import Embeddings
from qdrant_client import AsyncQdrantClient
from agentconnect.core.registry.registration import AgentRegistration
import uuid
import hashlib
import asyncio

# Configure logger
logger = logging.getLogger("CapabilityDiscovery.Indexing")


def _create_profile_text(registration: AgentRegistration) -> str:
    """Helper function to create a rich text representation of an agent's profile."""
    text_parts = [
        f"Agent Name: {registration.name}" if registration.name else None,
        f"Summary: {registration.summary}" if registration.summary else None,
        (
            f"Detailed Description: {registration.description}"
            if registration.description
            else None
        ),
    ]

    if registration.capabilities:
        cap_texts = [
            f"{cap.name}: {cap.description or 'No description.'}"
            for cap in registration.capabilities
        ]
        text_parts.append("Capabilities:\\n- " + "\\n- ".join(cap_texts))

    if registration.skills:
        skill_texts = [
            f"{skill.name}: {skill.description or 'No description.'}"
            for skill in registration.skills
        ]
        text_parts.append("Skills:\\n- " + "\\n- ".join(skill_texts))

    if registration.examples:
        text_parts.append("Usage Examples:\\n- " + "\\n- ".join(registration.examples))

    if registration.tags:
        text_parts.append("Tags: " + ", ".join(registration.tags))

    if registration.default_input_modes:
        text_parts.append(
            "Accepts Input Data Types: " + ", ".join(registration.default_input_modes)
        )

    if registration.default_output_modes:
        text_parts.append(
            "Produces Output Data Types: "
            + ", ".join(registration.default_output_modes)
        )

    if registration.auth_schemes:
        text_parts.append(
            "Supported Authentication: " + ", ".join(registration.auth_schemes)
        )

    # Filter out None or empty values before joining
    return "\\n\\n".join(filter(None, text_parts))


def string_to_uuid(string_id: str) -> str:
    """
    Convert a string ID to a UUID-compatible format by creating a deterministic hash.

    Args:
        string_id: The string ID to convert

    Returns:
        A UUID version 4 compatible string derived from the hash of the input string
    """
    # Create an MD5 hash of the string (16 bytes)
    hash_bytes = hashlib.md5(string_id.encode()).digest()

    # Set version bits for version 4 UUID (random)
    hash_bytes = bytearray(hash_bytes)
    hash_bytes[6] = (hash_bytes[6] & 0x0F) | 0x40  # Version 4
    hash_bytes[8] = (hash_bytes[8] & 0x3F) | 0x80  # Variant RFC4122

    # Convert back to bytes and create a UUID
    return str(uuid.UUID(bytes=bytes(hash_bytes)))


def _generate_points_for_registration(
    registration: AgentRegistration, embeddings_model: Embeddings
) -> Tuple[List[any], Dict[str, AgentRegistration]]:
    """
    Generates Qdrant PointStructs for an agent's profile, capabilities, and skills.
    Also returns a map of readable IDs to the registration object for these points.
    """
    # Import Qdrant models here to avoid circular imports at module level if not already there
    from qdrant_client.http import models as qdrant_models

    points = []
    local_capability_to_agent_map = {}
    agent_id = registration.agent_id

    # 1. Agent Profile Point
    profile_text = _create_profile_text(registration)
    profile_embedding = embeddings_model.embed_query(profile_text)
    readable_profile_id = f"{agent_id}_profile"
    qdrant_profile_id = string_to_uuid(readable_profile_id)

    profile_payload = {
        "agent_id": agent_id,
        "name": registration.name or "",
        "summary": registration.summary or "",
        "organization": registration.organization or "",
        "developer": registration.developer or "",
        "tags": (registration.tags if registration.tags else []),
        "auth_schemes": (
            registration.auth_schemes if registration.auth_schemes else []
        ),
        "default_input_modes": (
            registration.default_input_modes if registration.default_input_modes else []
        ),
        "default_output_modes": (
            registration.default_output_modes
            if registration.default_output_modes
            else []
        ),
        "payment_address": registration.payment_address or "",
        "doc_id": readable_profile_id,
        "doc_type": "agent_profile",
    }
    points.append(
        qdrant_models.PointStruct(
            id=qdrant_profile_id,
            vector=profile_embedding,
            payload=profile_payload,
        )
    )
    local_capability_to_agent_map[readable_profile_id] = registration

    # Common agent info for capability and skill payloads
    common_agent_payload_info = {
        "agent_id": agent_id,
        "agent_name": registration.name or agent_id,
        "agent_summary": registration.summary or "",
        "agent_url": registration.url or "",
        "agent_default_input_modes": (
            registration.default_input_modes if registration.default_input_modes else []
        ),
        "agent_default_output_modes": (
            registration.default_output_modes
            if registration.default_output_modes
            else []
        ),
        "agent_auth_schemes": (
            registration.auth_schemes if registration.auth_schemes else []
        ),
        "tags": (
            registration.tags if registration.tags else []
        ),  # Agent's tags for context
    }

    # 2. Capability Points
    if registration.capabilities:
        for idx, capability in enumerate(registration.capabilities):
            capability_text = f"{capability.name} {capability.description or ''}"
            capability_embedding = embeddings_model.embed_query(capability_text)
            readable_cap_id = f"{agent_id}:capability:{idx}:{capability.name}"
            qdrant_cap_id = string_to_uuid(readable_cap_id)

            cap_payload = {
                **common_agent_payload_info,
                "capability_name": capability.name,
                "capability_description": capability.description or "",
                "doc_id": readable_cap_id,
                "doc_type": "capability",
            }
            points.append(
                qdrant_models.PointStruct(
                    id=qdrant_cap_id,
                    vector=capability_embedding,
                    payload=cap_payload,
                )
            )
            local_capability_to_agent_map[readable_cap_id] = registration

    # 3. Skill Points
    if registration.skills:
        for idx, skill in enumerate(registration.skills):
            skill_text = f"{skill.name} {skill.description or ''}"
            skill_embedding = embeddings_model.embed_query(skill_text)
            readable_skill_id = f"{agent_id}:skill:{idx}:{skill.name}"
            qdrant_skill_id = string_to_uuid(readable_skill_id)

            skill_payload = {
                **common_agent_payload_info,
                "skill_name": skill.name,
                "skill_description": skill.description or "",
                "doc_id": readable_skill_id,
                "doc_type": "skill",
            }
            points.append(
                qdrant_models.PointStruct(
                    id=qdrant_skill_id,
                    vector=skill_embedding,
                    payload=skill_payload,
                )
            )
            local_capability_to_agent_map[readable_skill_id] = registration

    return points, local_capability_to_agent_map


async def precompute_all_capability_embeddings(
    async_client: AsyncQdrantClient,
    collection_name: str,
    embeddings_model: Embeddings,
    agent_registrations: Dict[str, AgentRegistration],
    batch_size: int = 100,
) -> Tuple[Dict[str, AgentRegistration], int]:
    """
    Precompute embeddings for all existing capabilities and store in Qdrant.

    Args:
        async_client: Initialized AsyncQdrantClient
        collection_name: Name of the collection to index into
        embeddings_model: Initialized embeddings model
        agent_registrations: Dictionary of agent registrations
        batch_size: Number of points to upload in each batch

    Returns:
        Tuple of (capability_to_agent_map, total_points_indexed)
    """
    if not embeddings_model or not agent_registrations or not async_client:
        logger.warning("Missing required components for indexing capabilities")
        return {}, 0

    logger.info("Precomputing embeddings for all existing capabilities...")

    # Process all agents to create points for Qdrant
    all_points_to_upsert = []
    capability_to_agent_map = {}

    # Track batch metrics
    current_batch_size = 0
    total_points_indexed = 0

    for agent_id, registration in agent_registrations.items():
        agent_points, agent_map_fragment = _generate_points_for_registration(
            registration, embeddings_model
        )
        all_points_to_upsert.extend(agent_points)
        capability_to_agent_map.update(agent_map_fragment)
        current_batch_size += len(agent_points)

        # Process in batches for better performance
        if current_batch_size >= batch_size:
            try:
                # Upload batch to Qdrant
                await async_client.upsert(
                    collection_name=collection_name, points=all_points_to_upsert
                )
                total_points_indexed += len(all_points_to_upsert)
                logger.debug(
                    f"Uploaded batch of {len(all_points_to_upsert)} points to Qdrant"
                )
                # Reset batch
                all_points_to_upsert = []
                current_batch_size = 0
            except Exception as batch_error:
                logger.error(f"Error uploading batch to Qdrant: {str(batch_error)}")

    # Upload any remaining points
    if all_points_to_upsert:
        try:
            await async_client.upsert(
                collection_name=collection_name, points=all_points_to_upsert
            )
            total_points_indexed += len(all_points_to_upsert)
            logger.debug(
                f"Uploaded final batch of {len(all_points_to_upsert)} points to Qdrant"
            )
        except Exception as batch_error:
            logger.error(f"Error uploading final batch to Qdrant: {str(batch_error)}")

    logger.info(
        f"Successfully indexed {total_points_indexed} points in Qdrant collection"
    )
    return capability_to_agent_map, total_points_indexed


async def update_capability_embeddings(
    async_client: AsyncQdrantClient,
    collection_name: str,
    embeddings_model: Embeddings,
    registration: AgentRegistration,
    capability_to_agent_map: Dict[str, AgentRegistration],
) -> Dict[str, AgentRegistration]:
    """
    Update capability embeddings for a registration in Qdrant.

    Args:
        async_client: Initialized AsyncQdrantClient
        collection_name: Name of the collection to update
        embeddings_model: Initialized embeddings model
        registration: Registration information for the agent
        capability_to_agent_map: Dictionary mapping doc_ids to agent registrations

    Returns:
        Updated capability_to_agent_map
    """

    agent_id = registration.agent_id
    logger.info(f"Updating embeddings for agent: {agent_id}")

    # First delete all existing points for this agent
    from agentconnect.core.registry.capability_discovery_impl.qdrant_client import (
        delete_points_by_agent_id,
    )

    await delete_points_by_agent_id(async_client, collection_name, agent_id)

    # Remove deleted points from capability_to_agent_map
    capability_to_agent_map_copy = capability_to_agent_map.copy()
    doc_ids_to_remove = [
        doc_id
        for doc_id in capability_to_agent_map_copy.keys()
        if doc_id.startswith(f"{agent_id}_profile") or doc_id.startswith(f"{agent_id}:")
    ]

    for doc_id in doc_ids_to_remove:
        del capability_to_agent_map[doc_id]

    # Generate new points and update the map
    new_points, agent_map_fragment = _generate_points_for_registration(
        registration, embeddings_model
    )
    capability_to_agent_map.update(agent_map_fragment)

    # Upload points to Qdrant
    if new_points:
        try:
            await async_client.upsert(
                collection_name=collection_name, points=new_points
            )
            logger.info(
                f"Updated embeddings for agent: {agent_id} with {len(new_points)} points"
            )
        except Exception as batch_error:
            logger.error(f"Error uploading points to Qdrant: {str(batch_error)}")
            import traceback

            logger.error(traceback.format_exc())

    return capability_to_agent_map


def extract_capability_index(
    agent_registrations: Dict[str, AgentRegistration],
) -> Dict[str, Set[str]]:
    """
    Extract a mapping of capability names to agent IDs.

    Args:
        agent_registrations: Dictionary of agent registrations

    Returns:
        Dictionary mapping capability names to sets of agent IDs
    """
    capability_index = {}

    for agent_id, registration in agent_registrations.items():
        for capability in registration.capabilities:
            capability_name = capability.name

            if capability_name not in capability_index:
                capability_index[capability_name] = set()

            capability_index[capability_name].add(agent_id)

    return capability_index


async def main():
    #  Test usage
    from agentconnect.core.registry.registration import AgentRegistration
    from agentconnect.core.types import (
        AgentType,
        InteractionMode,
        AgentIdentity,
        Skill,
        Capability,
    )

    # Removed direct AsyncQdrantClient import here, will use our helper
    from .qdrant_client import (
        initialize_qdrant_clients,
        init_qdrant_collection,
    )
    from .embedding_utils import (
        create_huggingface_embeddings,
    )

    registration = AgentRegistration(
        agent_id="test_agent",
        agent_type=AgentType.AI,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        identity=AgentIdentity.create_key_based(),
        name="Test Agent",
        summary="Test Agent Summary",
        description="Test Agent Description",
        version="1.0.0",
        documentation_url="https://test.com/test",
        organization="Test Organization",
        developer="Test Developer",
        url="https://test.com/test",
        auth_schemes=["OAuth2"],
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=[
            Capability(
                name="test_capability", description="Test Capability Description"
            )
        ],
        skills=[Skill(name="test_skill", description="Test Skill Description")],
        examples=["Test Example 1", "Test Example 2"],
        tags=["test_tag1", "test_tag2"],
        payment_address="0x1234567890123456789012345678901234567890",
        custom_metadata={"test_key": "test_value"},
    )

    # Initialize Qdrant clients using the helper function
    sync_client, async_client = await initialize_qdrant_clients({"in_memory": True})
    collection_name = "test_indexing_collection"  # Using a distinct name for this test
    embeddings_model = create_huggingface_embeddings(
        config={"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    )
    agent_registrations = {"test_agent": registration}
    collection_initialized = await init_qdrant_collection(
        async_client=async_client,
        embeddings_model=embeddings_model,
        collection_name=collection_name,
    )
    if not collection_initialized:
        print(f"Failed to initialize collection '{collection_name}'. Exiting test.")
        await async_client.close()
        return

    print(
        f"Successfully initialized Qdrant client and collection '{collection_name}' for testing."
    )

    # Test _create_profile_text
    profile_text = _create_profile_text(registration)
    print(
        "===========[Profile Text]===========\n",
        profile_text,
        "\n===========[Profile Text]===========",
    )

    # Test _generate_points_for_registration
    points, capability_to_agent_map_gen = _generate_points_for_registration(
        registration, embeddings_model
    )
    print("===========[Generated Points]===========")
    print(f"Generated {len(points)} points:")  # More concise
    for p in points:
        print(f"  ID: {p.id}, Type: {p.payload['doc_type']}")
    print("===========[Generated Points]===========")
    print("===========[Capability to Agent Map from _generate_points]===========")
    print(
        f"Map contains {len(capability_to_agent_map_gen)} entries. Keys: {list(capability_to_agent_map_gen.keys())}"
    )
    print("===========[Capability to Agent Map from _generate_points]===========")

    # Test precompute_all_capability_embeddings
    capability_to_agent_map_precomp, total_points_indexed = (
        await precompute_all_capability_embeddings(
            async_client, collection_name, embeddings_model, agent_registrations
        )
    )
    print("===========[Capability to Agent Map after precompute]===========")
    print(
        f"Map contains {len(capability_to_agent_map_precomp)} entries. Keys: {list(capability_to_agent_map_precomp.keys())}"
    )
    print("===========[Capability to Agent Map after precompute]===========")
    print(
        "===========[Total Points Indexed after precompute]===========\n",
        total_points_indexed,
        "\n===========[Total Points Indexed after precompute]===========",
    )

    # Modify registration for update test (e.g., add a new skill)
    updated_registration = registration  # Create a copy or modify
    updated_registration.skills.append(
        Skill(name="new_skill", description="A newly added skill for testing update.")
    )
    updated_registration.tags.append("updated_tag")

    # Test update_capability_embeddings
    capability_to_agent_map_updated = await update_capability_embeddings(
        async_client,
        collection_name,
        embeddings_model,
        updated_registration,
        capability_to_agent_map_precomp,
    )
    print("===========[Capability to Agent Map after update]===========")
    print(
        f"Map contains {len(capability_to_agent_map_updated)} entries. Keys: {list(capability_to_agent_map_updated.keys())}"
    )
    print("===========[Capability to Agent Map after update]===========")

    # Test extract_capability_index
    capability_index = extract_capability_index(
        agent_registrations
    )  # Uses the original or updated registration based on what you want to test
    print(
        "===========[Capability Index]===========\n",
        capability_index,
        "\n===========[Capability Index]===========",
    )

    await async_client.close()  # Close the client when done


if __name__ == "__main__":
    asyncio.run(main())  # Run the async main function
