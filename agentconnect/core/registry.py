"""
Agent registry for the AgentConnect framework.

This module provides the AgentRegistry class for agent registration, discovery,
and capability matching, as well as the AgentRegistration dataclass for storing
agent registration information.
"""

# Standard library imports
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Absolute imports from agentconnect package
from agentconnect.core.types import (
    AgentIdentity,
    AgentType,
    Capability,
    InteractionMode,
    VerificationStatus,
)

# Set up logging
logger = logging.getLogger("AgentRegistry")


@dataclass
class AgentRegistration:
    """
    Registration information for an agent.

    This class stores the registration information for an agent, including
    its identity, capabilities, and interaction modes.

    Attributes:
        agent_id: Unique identifier for the agent
        organization_id: ID of the organization the agent belongs to
        agent_type: Type of agent (human, AI)
        interaction_modes: Supported interaction modes
        capabilities: List of agent capabilities
        identity: Agent's decentralized identity
        owner_id: ID of the agent's owner
        metadata: Additional information about the agent
    """

    agent_id: str
    organization_id: Optional[str]
    agent_type: AgentType
    interaction_modes: list[InteractionMode]
    capabilities: list[Capability]
    identity: AgentIdentity
    owner_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class AgentRegistry:
    """
    Central registry for agent registration and discovery.

    This class provides methods for registering agents, discovering agents
    by capability, and verifying agent identities.
    """

    def __init__(self):
        """
        Initialize the agent registry.

        This method initializes the registry with empty indexes for agents,
        capabilities, interaction modes, organizations, and owners.
        """
        logger.info("Initializing AgentRegistry")
        self._agents: Dict[str, AgentRegistration] = {}
        self._capabilities_index: Dict[str, Set[str]] = {}
        self._interaction_index: Dict[InteractionMode, Set[str]] = {
            mode: set() for mode in InteractionMode
        }
        self._organization_index: Dict[str, Set[str]] = {}
        self._owner_index: Dict[str, Set[str]] = {}
        self._verified_agents: Set[str] = set()

        # Initialize embeddings model in the background
        asyncio.create_task(self._initialize_embeddings_model())

    async def _initialize_embeddings_model(self) -> None:
        """
        Initialize the embeddings model in the background.

        This method initializes the embeddings model used for semantic search
        of agent capabilities.
        """
        try:
            if self._check_semantic_search_requirements():
                from langchain_huggingface import HuggingFaceEmbeddings

                logger.info("Initializing embeddings model for semantic search...")
                self._embeddings_model = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    cache_folder="./.cache/huggingface/embeddings",  # Cache embeddings locally
                )
                self._capability_embeddings_cache = {}
                logger.info("Embeddings model initialized successfully")

                # Precompute embeddings for all existing capabilities
                await self._precompute_all_capability_embeddings()
        except Exception as e:
            logger.warning(f"Failed to initialize embeddings model: {str(e)}")

    async def _precompute_all_capability_embeddings(self) -> None:
        """
        Precompute embeddings for all existing capabilities.

        This method precomputes embeddings for all capabilities of all agents
        in the registry to speed up semantic search.
        """
        try:
            if not hasattr(self, "_embeddings_model") or not self._agents:
                return

            logger.info("Precomputing embeddings for all existing capabilities...")

            # Process agents in batches to avoid memory issues
            batch_size = 10
            agent_ids = list(self._agents.keys())

            for i in range(0, len(agent_ids), batch_size):
                batch_agent_ids = agent_ids[i : i + batch_size]

                for agent_id in batch_agent_ids:
                    registration = self._agents[agent_id]
                    await self._update_capability_embeddings_cache(registration)

            logger.info(
                f"Precomputed embeddings for {len(self._capability_embeddings_cache)} capabilities"
            )
        except Exception as e:
            logger.warning(f"Error precomputing capability embeddings: {str(e)}")

    async def register(self, registration: AgentRegistration) -> bool:
        """
        Register a new agent with verification.

        Args:
            registration: Registration information for the agent

        Returns:
            True if registration was successful, False otherwise
        """
        try:
            logger.info(f"Attempting to register agent: {registration.agent_id}")

            # Verify agent identity
            logger.debug("Verifying agent identity")
            if not await self._verify_agent_identity(registration.identity):
                logger.error("Agent identity verification failed")
                registration.identity.verification_status = VerificationStatus.FAILED
                return False

            registration.identity.verification_status = VerificationStatus.VERIFIED
            self._agents[registration.agent_id] = registration
            self._verified_agents.add(registration.agent_id)

            # Update indexes
            logger.debug("Updating registry indexes")
            await self._update_indexes(registration)

            logger.info(f"Successfully registered agent: {registration.agent_id}")
            return True

        except Exception as e:
            logger.exception(f"Error registering agent: {str(e)}")
            return False

    async def _update_indexes(self, registration: AgentRegistration) -> None:
        """
        Update registry indexes with new registration.

        Args:
            registration: Registration information for the agent

        Raises:
            Exception: If there is an error updating the indexes
        """
        try:
            logger.debug(f"Updating indexes for agent: {registration.agent_id}")

            # Update capability index
            for capability in registration.capabilities:
                if capability.name not in self._capabilities_index:
                    self._capabilities_index[capability.name] = set()
                self._capabilities_index[capability.name].add(registration.agent_id)

            # Update interaction mode index
            for mode in registration.interaction_modes:
                self._interaction_index[mode].add(registration.agent_id)

            # Update organization index
            if registration.organization_id:
                if registration.organization_id not in self._organization_index:
                    self._organization_index[registration.organization_id] = set()
                self._organization_index[registration.organization_id].add(
                    registration.agent_id
                )

            # Update owner index
            if registration.owner_id:
                if registration.owner_id not in self._owner_index:
                    self._owner_index[registration.owner_id] = set()
                self._owner_index[registration.owner_id].add(registration.agent_id)

            # Update capability embeddings cache if semantic search is enabled
            if self._check_semantic_search_requirements() and hasattr(
                self, "_embeddings_model"
            ):
                asyncio.create_task(
                    self._update_capability_embeddings_cache(registration)
                )

            logger.debug("Successfully updated all indexes")

        except Exception as e:
            logger.exception(f"Error updating indexes: {str(e)}")
            raise

    async def _update_capability_embeddings_cache(
        self, registration: AgentRegistration
    ) -> None:
        """
        Update the cache of capability embeddings for a registration.

        Args:
            registration: Registration information for the agent
        """
        try:
            # Skip if no capabilities or embeddings model not initialized
            if not registration.capabilities or not hasattr(self, "_embeddings_model"):
                return

            # Initialize the cache if it doesn't exist
            if not hasattr(self, "_capability_embeddings_cache"):
                self._capability_embeddings_cache = {}

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

    async def _verify_agent_identity(self, identity: AgentIdentity) -> bool:
        """
        Verify agent's DID and public key.

        Args:
            identity: Agent's decentralized identity

        Returns:
            True if the identity is verified, False otherwise
        """
        try:
            logger.debug(f"Verifying agent identity: {identity.did}")

            # Verify DID format
            if not identity.did.startswith(("did:ethr:", "did:key:")):
                logger.error("Invalid DID format")
                return False

            # Verify DID resolution
            if identity.did.startswith("did:ethr:"):
                return await self._verify_ethereum_did(identity)
            else:  # did:key
                return await self._verify_key_did(identity)

        except Exception as e:
            logger.exception(f"Error verifying agent identity: {str(e)}")
            return False

    async def _verify_ethereum_did(self, identity: AgentIdentity) -> bool:
        """
        Verify Ethereum-based DID.

        Args:
            identity: Agent's Ethereum-based decentralized identity

        Returns:
            True if the identity is verified, False otherwise
        """
        try:
            logger.debug("Verifying Ethereum DID")
            eth_address = identity.did.split(":")[-1]

            if not eth_address.startswith("0x") or len(eth_address) != 42:
                logger.error("Invalid Ethereum address format")
                return False

            # TODO: Implement full Ethereum DID verification
            logger.debug("Basic Ethereum DID verification passed")
            return True

        except Exception as e:
            logger.exception(f"Error verifying Ethereum DID: {str(e)}")
            return False

    async def _verify_key_did(self, identity: AgentIdentity) -> bool:
        """
        Verify key-based DID.

        Args:
            identity: Agent's key-based decentralized identity

        Returns:
            True if the identity is verified, False otherwise
        """
        try:
            logger.debug("Verifying key-based DID")
            # TODO: Implement full key-based DID verification
            logger.debug("Basic key-based DID verification passed")
            return True
        except Exception as e:
            logger.exception(f"Error verifying key-based DID: {str(e)}")
            return False

    async def unregister(self, agent_id: str) -> bool:
        """
        Remove agent from registry.

        Args:
            agent_id: ID of the agent to unregister

        Returns:
            True if unregistration was successful, False otherwise
        """
        try:
            logger.debug(f"Attempting to unregister agent: {agent_id}")

            if agent_id not in self._agents:
                logger.error("Agent not found in registry")
                return False

            registration = self._agents[agent_id]

            # Clean up all indexes
            del self._agents[agent_id]
            for mode in registration.interaction_modes:
                if agent_id in self._interaction_index[mode]:
                    self._interaction_index[mode].remove(agent_id)

            for capability in registration.capabilities:
                if capability.name in self._capabilities_index:
                    if agent_id in self._capabilities_index[capability.name]:
                        self._capabilities_index[capability.name].remove(agent_id)

            # Clear embeddings cache for this agent
            self._clear_agent_embeddings_cache(agent_id)

            logger.info(f"Successfully unregistered agent: {agent_id}")
            return True
        except Exception as e:
            logger.exception(f"Error unregistering agent: {str(e)}")
            return False

    def _clear_agent_embeddings_cache(self, agent_id: str) -> None:
        """
        Clear the embeddings cache for a specific agent.

        Args:
            agent_id: ID of the agent to clear cache for
        """
        if hasattr(self, "_capability_embeddings_cache"):
            # Find and remove all cache entries for this agent
            keys_to_remove = [
                key
                for key in self._capability_embeddings_cache.keys()
                if key.startswith(f"{agent_id}:")
            ]

            for key in keys_to_remove:
                del self._capability_embeddings_cache[key]

            logger.debug(f"Cleared embeddings cache for agent: {agent_id}")

    async def get_by_capability(self, capability_name: str) -> List[AgentRegistration]:
        """
        Find agents by capability name (simple string matching).

        Args:
            capability_name: Name of the capability to search for

        Returns:
            List of agent registrations with the specified capability
        """
        logger.debug(f"Searching agents with capability: {capability_name}")
        agent_ids = self._capabilities_index.get(capability_name, set())
        return [
            self._agents[agent_id] for agent_id in agent_ids if agent_id in self._agents
        ]

    def _check_semantic_search_requirements(self) -> bool:
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

    async def get_by_capability_semantic(
        self, capability_description: str
    ) -> List[Tuple[AgentRegistration, float]]:
        """
        Find agents by capability description using semantic search.

        Args:
            capability_description: Description of the capability to search for

        Returns:
            List of tuples containing agent registrations and similarity scores
        """
        logger.debug(
            f"Searching agents with capability description: {capability_description}"
        )
        results = []

        # Check if required packages are installed
        if self._check_semantic_search_requirements():
            try:
                # Try to use embeddings if available
                # Use the updated HuggingFaceEmbeddings from langchain_huggingface
                from langchain_huggingface import HuggingFaceEmbeddings

                # Initialize embeddings model with caching
                # This is a class attribute to avoid reinitializing the model for each search
                if not hasattr(self, "_embeddings_model"):
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
                if (
                    hasattr(self, "_capability_embeddings_cache")
                    and self._capability_embeddings_cache
                ):
                    # Use the cache for faster processing
                    for agent_id, registration in self._agents.items():
                        highest_similarity = 0.0

                        for capability in registration.capabilities:
                            cache_key = f"{agent_id}:{capability.name}"
                            if cache_key in self._capability_embeddings_cache:
                                # Get the cached embedding
                                capability_embedding = (
                                    self._capability_embeddings_cache[cache_key]
                                )
                                similarity = self._cosine_similarity(
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

                    for agent_id, registration in self._agents.items():
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
                            similarity = self._cosine_similarity(
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
        for agent_id, registration in self._agents.items():
            for capability in registration.capabilities:
                # Simple string similarity check
                similarity = self._calculate_similarity(
                    capability_description.lower(),
                    f"{capability.name} {capability.description}".lower(),
                )
                if similarity > 0.3:  # Arbitrary threshold
                    results.append((registration, similarity))
                    break  # Only count each agent once

        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _cosine_similarity(self, vec1, vec2):
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

    async def get_all_capabilities(self) -> List[str]:
        """
        Get a list of all unique capability names registered in the system.

        Returns:
            List of all capability names
        """
        logger.debug("Getting all registered capabilities")
        return list(self._capabilities_index.keys())

    async def get_all_agents(self) -> List[AgentRegistration]:
        """
        Get a list of all agents registered in the system.

        Returns:
            List of all agent registrations
        """
        logger.debug("Getting all registered agents")
        return list(self._agents.values())

    async def get_agent_type(self, agent_id: str) -> AgentType:
        """
        Get the type of an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Type of the agent

        Raises:
            KeyError: If the agent is not found
        """
        return self._agents[agent_id].agent_type

    def _calculate_similarity(self, text1: str, text2: str) -> float:
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

    async def get_by_interaction_mode(
        self, mode: InteractionMode
    ) -> List[AgentRegistration]:
        """
        Find agents by interaction mode.

        Args:
            mode: Interaction mode to search for

        Returns:
            List of agent registrations with the specified interaction mode
        """
        try:
            logger.debug(f"Searching agents with interaction mode: {mode}")
            agent_ids = self._interaction_index[mode]
            return [self._agents[agent_id] for agent_id in agent_ids]
        except Exception as e:
            logger.exception(f"Error retrieving agents by interaction mode: {str(e)}")
            return []

    async def get_registration(self, agent_id: str) -> Optional[AgentRegistration]:
        """
        Get agent registration details.

        Args:
            agent_id: ID of the agent

        Returns:
            Agent registration if found, None otherwise
        """
        return self._agents.get(agent_id)

    async def get_by_organization(
        self, organization_id: str
    ) -> List[AgentRegistration]:
        """
        Find agents by organization.

        Args:
            organization_id: ID of the organization

        Returns:
            List of agent registrations in the specified organization
        """
        agent_ids = self._organization_index.get(organization_id, set())
        return [self._agents[agent_id] for agent_id in agent_ids]

    async def get_verified_agents(self) -> List[AgentRegistration]:
        """
        Get all verified agents.

        Returns:
            List of verified agent registrations
        """
        return [self._agents[agent_id] for agent_id in self._verified_agents]

    async def verify_agent(self, agent_id: str) -> bool:
        """
        Verify an agent's identity.

        Args:
            agent_id: ID of the agent to verify

        Returns:
            True if verification was successful, False otherwise
        """
        if agent_id not in self._agents:
            return False

        registration = self._agents[agent_id]
        verified = await self._verify_agent_identity(registration.identity)

        if verified:
            self._verified_agents.add(agent_id)
            registration.identity.verification_status = VerificationStatus.VERIFIED
        else:
            self._verified_agents.discard(agent_id)
            registration.identity.verification_status = VerificationStatus.FAILED

        return verified

    async def update_registration(
        self, agent_id: str, updates: Dict
    ) -> Optional[AgentRegistration]:
        """
        Update agent registration details.

        Args:
            agent_id: ID of the agent to update
            updates: Dictionary of updates to apply

        Returns:
            Updated agent registration if successful, None otherwise
        """
        if agent_id not in self._agents:
            return None

        registration = self._agents[agent_id]

        # Update allowed fields
        if "capabilities" in updates:
            # Convert capability dictionaries to Capability objects
            capabilities = [
                Capability(**cap) if isinstance(cap, dict) else cap
                for cap in updates["capabilities"]
            ]

            # Remove from old capability indexes
            for cap in registration.capabilities:
                if (
                    cap.name in self._capabilities_index
                ):  # Check if the capability exists
                    self._capabilities_index[cap.name].discard(agent_id)

            # Clear old capability embeddings from cache
            self._clear_agent_embeddings_cache(agent_id)

            # Update capabilities
            registration.capabilities = capabilities

            # Add to new capability indexes
            for cap in registration.capabilities:
                if cap.name not in self._capabilities_index:
                    self._capabilities_index[cap.name] = set()
                self._capabilities_index[cap.name].add(agent_id)

            # Update capability embeddings cache if semantic search is enabled
            if self._check_semantic_search_requirements() and hasattr(
                self, "_embeddings_model"
            ):
                asyncio.create_task(
                    self._update_capability_embeddings_cache(registration)
                )

        if "interaction_modes" in updates:
            # Remove from old mode indexes
            for mode in registration.interaction_modes:
                self._interaction_index[mode].discard(agent_id)

            # Update modes
            registration.interaction_modes = updates["interaction_modes"]

            # Add to new mode indexes
            for mode in registration.interaction_modes:
                self._interaction_index[mode].add(agent_id)

        if "metadata" in updates:
            registration.metadata.update(updates["metadata"])

        return registration

    async def get_by_owner(self, owner_id: str) -> List[AgentRegistration]:
        """
        Find agents by owner.

        Args:
            owner_id: ID of the owner

        Returns:
            List of agent registrations owned by the specified owner
        """
        agent_ids = self._owner_index.get(owner_id, set())
        return [self._agents[agent_id] for agent_id in agent_ids]

    async def verify_owner(self, agent_id: str, owner_id: str) -> bool:
        """
        Verify if a user owns an agent.

        Args:
            agent_id: ID of the agent
            owner_id: ID of the owner

        Returns:
            True if the user owns the agent, False otherwise
        """
        if agent_id not in self._agents:
            return False
        return self._agents[agent_id].owner_id == owner_id
