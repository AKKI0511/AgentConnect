import logging
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, field

from src.core.types import AgentIdentity, AgentType, InteractionMode, VerificationStatus
from src.utils.logging_config import LogLevel, setup_logging

# Configure logging
setup_logging(level=LogLevel.DEBUG, module_levels={"AgentRegistry": LogLevel.DEBUG})
logger = logging.getLogger("AgentRegistry")


@dataclass
class AgentRegistration:
    agent_id: str
    organization_id: Optional[str]
    agent_type: AgentType
    interaction_modes: list[InteractionMode]
    capabilities: list[str]
    identity: AgentIdentity
    metadata: Dict = field(default_factory=dict)


class AgentRegistry:
    """Central registry for agent registration and discovery"""

    def __init__(self):
        logger.info("Initializing AgentRegistry")
        self._agents: Dict[str, AgentRegistration] = {}
        self._capabilities_index: Dict[str, Set[str]] = {}
        self._interaction_index: Dict[InteractionMode, Set[str]] = {
            mode: set() for mode in InteractionMode
        }
        self._organization_index: Dict[str, Set[str]] = {}
        self._verified_agents: Set[str] = set()

    async def register(self, registration: AgentRegistration) -> bool:
        """Register a new agent with verification"""
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
        """Update registry indexes with new registration"""
        try:
            logger.debug(f"Updating indexes for agent: {registration.agent_id}")

            # Update capability index
            for capability in registration.capabilities:
                if capability not in self._capabilities_index:
                    self._capabilities_index[capability] = set()
                self._capabilities_index[capability].add(registration.agent_id)

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

            logger.debug("Successfully updated all indexes")

        except Exception as e:
            logger.exception(f"Error updating indexes: {str(e)}")
            raise

    async def _verify_agent_identity(self, identity: AgentIdentity) -> bool:
        """Verify agent's DID and public key"""
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
        """Verify Ethereum-based DID"""
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
        """Verify key-based DID"""
        try:
            logger.debug("Verifying key-based DID")
            # TODO: Implement full key-based DID verification
            logger.debug("Basic key-based DID verification passed")
            return True
        except Exception as e:
            logger.exception(f"Error verifying key-based DID: {str(e)}")
            return False

    async def unregister(self, agent_id: str) -> bool:
        """Remove agent from registry"""
        try:
            logger.debug(f"Attempting to unregister agent: {agent_id}")

            if agent_id not in self._agents:
                logger.error("Agent not found in registry")
                return False

            registration = self._agents[agent_id]

            # Clean up all indexes
            del self._agents[agent_id]
            self._interaction_index[registration.interaction_mode].remove(agent_id)

            for capability in registration.capabilities:
                if agent_id in self._capabilities_index[capability]:
                    self._capabilities_index[capability].remove(agent_id)

            logger.info(f"Successfully unregistered agent: {agent_id}")
            return True
        except Exception as e:
            logger.exception(f"Error unregistering agent: {str(e)}")
            return False

    async def get_by_capability(self, capability: str) -> List[AgentRegistration]:
        """Find agents by capability"""
        try:
            logger.debug(f"Searching agents with capability: {capability}")
            agent_ids = self._capabilities_index.get(capability, set())
            return [self._agents[agent_id] for agent_id in agent_ids]
        except Exception as e:
            logger.exception(f"Error retrieving agents by capability: {str(e)}")
            return []

    async def get_by_interaction_mode(
        self, mode: InteractionMode
    ) -> List[AgentRegistration]:
        """Find agents by interaction mode"""
        try:
            logger.debug(f"Searching agents with interaction mode: {mode}")
            agent_ids = self._interaction_index[mode]
            return [self._agents[agent_id] for agent_id in agent_ids]
        except Exception as e:
            logger.exception(f"Error retrieving agents by interaction mode: {str(e)}")
            return []

    async def get_registration(self, agent_id: str) -> Optional[AgentRegistration]:
        """Get agent registration details"""
        return self._agents.get(agent_id)

    async def get_by_organization(
        self, organization_id: str
    ) -> List[AgentRegistration]:
        """Find agents by organization"""
        agent_ids = self._organization_index.get(organization_id, set())
        return [self._agents[agent_id] for agent_id in agent_ids]

    async def get_verified_agents(self) -> List[AgentRegistration]:
        """Get all verified agents"""
        return [self._agents[agent_id] for agent_id in self._verified_agents]

    async def verify_agent(self, agent_id: str) -> bool:
        """Verify an agent's identity"""
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
        """Update agent registration details"""
        if agent_id not in self._agents:
            return None

        registration = self._agents[agent_id]

        # Update allowed fields
        if "capabilities" in updates:
            # Remove from old capability indexes
            for cap in registration.capabilities:
                self._capabilities_index[cap].discard(agent_id)

            # Update capabilities
            registration.capabilities = updates["capabilities"]

            # Add to new capability indexes
            for cap in registration.capabilities:
                if cap not in self._capabilities_index:
                    self._capabilities_index[cap] = set()
                self._capabilities_index[cap].add(agent_id)

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
