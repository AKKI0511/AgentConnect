"""
Agent registry for the AgentConnect framework.

This module provides the AgentRegistry class for agent registration, discovery,
and capability matching.
"""

# Standard library imports
import asyncio
import logging
import os
from typing import Dict, List, Optional, Set, Tuple, Any

# Absolute imports from agentconnect package
from agentconnect.core.types import (
    AgentType,
    Capability,
    InteractionMode,
    VerificationStatus,
)
from agentconnect.core.registry.registration import AgentRegistration
from agentconnect.core.registry.capability_discovery import CapabilityDiscoveryService
from agentconnect.core.registry.identity_verification import (
    verify_agent_identity,
)

# Set up logging
logger = logging.getLogger("AgentRegistry")


class AgentRegistry:
    """
    Central registry for agent registration and discovery.

    This class provides methods for registering agents, discovering agents
    by capability, and verifying agent identities.
    """

    def __init__(self, vector_search_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent registry.

        This method initializes the registry with empty indexes for agents,
        capabilities, interaction modes, organizations, and owners.

        Args:
            vector_search_config: Optional configuration for vector search capability
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

        # Set default vector search configuration if not provided
        if vector_search_config is None:
            vector_search_config = {
                "model_name": "sentence-transformers/all-mpnet-base-v2",
                "cache_folder": "./.cache/huggingface/embeddings",
                "prefer_backend": "faiss",  # Use FAISS by default (falls back to USearch if available)
                "vector_store_path": "./.cache/vector_stores",
            }

        # Initialize capability discovery service with configuration
        self._capability_discovery = CapabilityDiscoveryService(vector_search_config)
        self._vector_search_config = vector_search_config

        # Create vector store directory if it doesn't exist
        os.makedirs(
            vector_search_config.get("vector_store_path", "./.cache/vector_stores"),
            exist_ok=True,
        )

        # Initialize embeddings model and try to load existing vector store
        asyncio.create_task(self._initialize_vector_search())

    async def _initialize_vector_search(self) -> None:
        """
        Initialize vector search capabilities.

        This method:

        1. Initializes the embeddings model
        2. Attempts to load existing vector store from disk
        3. If loading fails, precomputes embeddings for all existing capabilities
        """
        try:
            # Initialize the embeddings model first
            await self._capability_discovery.initialize_embeddings_model()

            # Try to load existing vector store if available
            vector_store_path = self._vector_search_config.get("vector_store_path")

            if vector_store_path:
                try:
                    success = await self._capability_discovery.load_vector_store(
                        vector_store_path
                    )
                    if success:
                        logger.info(
                            f"Successfully loaded vector store from {vector_store_path}"
                        )
                        # Still need to populate the capability map
                        if self._agents:
                            for agent_id, registration in self._agents.items():
                                for capability in registration.capabilities:
                                    doc_id = f"{agent_id}:{capability.name}"
                                    self._capability_discovery._capability_to_agent_map[
                                        doc_id
                                    ] = registration
                        return
                    else:
                        logger.info(
                            "Could not load vector store, will precompute embeddings"
                        )
                except Exception as e:
                    logger.warning(f"Failed to load vector store: {str(e)}")

            # Precompute embeddings for all existing capabilities
            if self._agents:
                await self._capability_discovery.precompute_all_capability_embeddings(
                    self._agents
                )

                # Try to save the computed vector store for future use
                if vector_store_path:
                    try:
                        await self._capability_discovery.save_vector_store(
                            vector_store_path
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save vector store: {str(e)}")
        except Exception as e:
            logger.exception(f"Error initializing vector search: {str(e)}")

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
            if not await verify_agent_identity(registration.identity):
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

            # Try to save the updated vector store
            vector_store_path = self._vector_search_config.get("vector_store_path")
            if vector_store_path:
                asyncio.create_task(
                    self._capability_discovery.save_vector_store(vector_store_path)
                )

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

            # Update capability embeddings cache
            asyncio.create_task(
                self._capability_discovery.update_capability_embeddings_cache(
                    registration
                )
            )

            logger.debug("Successfully updated all indexes")

        except Exception as e:
            logger.exception(f"Error updating indexes: {str(e)}")
            raise

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
            self._capability_discovery.clear_agent_embeddings_cache(agent_id)

            # Try to save the updated vector store
            vector_store_path = self._vector_search_config.get("vector_store_path")
            if vector_store_path:
                asyncio.create_task(
                    self._capability_discovery.save_vector_store(vector_store_path)
                )

            logger.info(f"Successfully unregistered agent: {agent_id}")
            return True
        except Exception as e:
            logger.exception(f"Error unregistering agent: {str(e)}")
            return False

    async def get_by_capability(
        self, capability_name: str, limit: int = 10, similarity_threshold: float = 0.1
    ) -> List[AgentRegistration]:
        """
        Find agents by capability name.

        Args:
            capability_name: Name of the capability to search for
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score for semantic fallback search (default: 0.1)

        Returns:
            List of agent registrations with the specified capability
        """
        return await self._capability_discovery.find_by_capability_name(
            capability_name,
            self._agents,
            self._capabilities_index,
            limit,
            similarity_threshold,
        )

    async def get_by_capability_semantic(
        self,
        capability_description: str,
        limit: int = 10,
        similarity_threshold: float = 0.1,
    ) -> List[Tuple[AgentRegistration, float]]:
        """
        Find agents by capability description using semantic search.

        Args:
            capability_description: Description of the capability to search for
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score to include in results (default: 0.1)

        Returns:
            List of tuples containing agent registrations and similarity scores
        """
        return await self._capability_discovery.find_by_capability_semantic(
            capability_description, self._agents, limit, similarity_threshold
        )

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
        verified = await verify_agent_identity(registration.identity)

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
            self._capability_discovery.clear_agent_embeddings_cache(agent_id)

            # Update capabilities
            registration.capabilities = capabilities

            # Add to new capability indexes
            for cap in registration.capabilities:
                if cap.name not in self._capabilities_index:
                    self._capabilities_index[cap.name] = set()
                self._capabilities_index[cap.name].add(agent_id)

            # Update capability embeddings cache
            asyncio.create_task(
                self._capability_discovery.update_capability_embeddings_cache(
                    registration
                )
            )

            # Try to save the updated vector store
            vector_store_path = self._vector_search_config.get("vector_store_path")
            if vector_store_path:
                asyncio.create_task(
                    self._capability_discovery.save_vector_store(vector_store_path)
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

        # Update payment address if provided
        if "payment_address" in updates:
            registration.payment_address = updates["payment_address"]

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
