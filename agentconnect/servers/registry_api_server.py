"""
Registry API Server for AgentConnect

This server provides a REST API for the AgentConnect Registry, allowing agents to register, search, and manage their own metadata.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# AgentConnect core imports
from agentconnect.core.registry import AgentRegistry, AgentRegistration
from agentconnect.core.registry.search import (
    AgentSearchInput,
    AgentSearchOutput,
    populate_search_result_item,
)
from agentconnect.core.types import Capability, InteractionMode, AgentType, Skill
from agentconnect.servers.config import RegistryAPISettings

logger = logging.getLogger("uvicorn.error.agentconnect.registry")

# Global variable to hold the registry instance, initialized via lifespan
_agent_registry_instance: Optional[AgentRegistry] = None


def create_registry_api_app(
    settings: Optional[RegistryAPISettings] = None,
) -> FastAPI:
    """Factory to create a FastAPI app for the Registry API.

    - If settings is None, load from environment using RegistryAPISettings().
    - Configures CORS and lifespan using the provided settings.
    """

    resolved_settings = settings or RegistryAPISettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[override]
        global _agent_registry_instance
        # Apply our logger level at lifespan start so it reflects runtime settings
        logger.setLevel(getattr(logging, resolved_settings.log_level))
        logger.info("Starting AgentConnect Registry API Server...")

        # Create vector search settings based on server configuration
        vector_search_settings = resolved_settings.vector_search

        logger.debug(
            "Using vector search settings: %s", vector_search_settings.model_name
        )
        logger.debug(
            "Vector store type: %s",
            vector_search_settings.deployment.type,
        )

        _agent_registry_instance = AgentRegistry(
            vector_search_config=vector_search_settings
        )
        await _agent_registry_instance.ensure_initialized()
        logger.info("AgentRegistry initialized and ready for API Server.")
        yield
        # Clean up resources if any (e.g., closing vector store if not in-memory)
        logger.info("AgentRegistry API Server shutting down.")
        _agent_registry_instance = None

    app = FastAPI(
        title="AgentConnect Registry API Server",
        description="Provides API access to an AgentRegistry instance.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(router)

    # Attach resolved settings for introspection if needed by host environments
    app.state.registry_settings = resolved_settings

    return app


# Router and models
router = APIRouter()


# Pydantic model for the update payload
class AgentRegistrationUpdatePayload(BaseModel):
    """Agent registration update payload."""

    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    documentation_url: Optional[str] = None
    organization: Optional[str] = None
    developer: Optional[str] = None
    url: Optional[str] = None
    auth_schemes: Optional[List[str]] = None
    interaction_modes: Optional[List[InteractionMode]] = None
    default_input_modes: Optional[List[str]] = None
    default_output_modes: Optional[List[str]] = None
    capabilities: Optional[List[Capability]] = None
    skills: Optional[List[Skill]] = None
    examples: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    payment_address: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic model configuration."""

        use_enum_values = True


def get_registry() -> AgentRegistry:
    """Dependency injector for AgentRegistry instance."""
    if _agent_registry_instance is None:
        # This should not happen if lifespan event worked correctly
        raise HTTPException(status_code=500, detail="AgentRegistry not initialized")
    return _agent_registry_instance


# --- Health Check Endpoint ---
@router.get(
    "/health",
    status_code=200,
    summary="Check server health and registry initialization status",
    tags=["Server Health"],
)
async def health_check_endpoint():
    """
    Checks the operational status of the server and its core components.
    - Returns "healthy" if the server is running and the AgentRegistry is fully initialized.
    - Returns "initializing" if the AgentRegistry is still loading its dependencies.
    - Will return a 500 error via `get_registry()` if the registry instance is not available at all.
    """
    registry = (
        get_registry()
    )  # Ensures _agent_registry_instance is not None and FastAPI app is up
    if (
        registry._initialized_event.is_set()
    ):  # Accessing _initialized_event from AgentRegistry instance
        return {"status": "healthy", "registry_status": "initialized_and_ready"}
    else:
        # This state means FastAPI is up, _agent_registry_instance exists (returned by get_registry),
        # but its internal async _initialize_vector_search task (and thus _initialized_event) hasn't completed.
        return {
            "status": "initializing",
            "registry_status": "core_dependencies_initializing",
        }


# --- API Endpoints ---


@router.get(
    "/agents/verified",
    response_model=List[AgentRegistration],
    summary="Get all verified agents",
    tags=["Agent Properties"],
)
async def get_verified_agents_endpoint() -> List[AgentRegistration]:
    registry = get_registry()
    try:
        return await registry.get_verified_agents()
    except Exception as e:
        logger.error("Error getting verified agents", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error getting verified agents: {str(e)}"
        )


@router.post(
    "/agents/register", status_code=201, summary="Register a new agent", tags=["Agents"]
)
async def register_agent_endpoint(
    registration_data: AgentRegistration,
) -> Dict[str, Any]:
    registry = get_registry()
    try:
        success = await registry.register(registration_data)
        if success:
            return {
                "message": "Agent registered successfully",
                "agent_id": registration_data.agent_id,
            }
        else:
            # Check if already registered or other reason for failure
            existing_reg = await registry.get_registration(registration_data.agent_id)
            if existing_reg:
                raise HTTPException(
                    status_code=409,
                    detail=f"Agent with ID {registration_data.agent_id} already registered.",
                )
            raise HTTPException(
                status_code=400,
                detail="Agent registration failed for an unknown reason.",
            )
    except Exception as e:
        logger.error(
            "Error registering agent agent_id=%s",
            registration_data.agent_id,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agents/{agent_id}",
    response_model=Optional[AgentRegistration],
    summary="Get agent registration details",
    tags=["Agents"],
)
async def get_agent_registration_endpoint(agent_id: str) -> Optional[AgentRegistration]:
    registry = get_registry()
    registration = await registry.get_registration(agent_id)
    if not registration:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID {agent_id} not found."
        )
    return registration


@router.get(
    "/agents",
    response_model=List[AgentRegistration],
    summary="Get all registered agents",
    tags=["Agents"],
)
async def get_all_agents_endpoint() -> List[AgentRegistration]:
    registry = get_registry()
    return await registry.get_all_agents()


@router.put(
    "/agents/{agent_id}",
    response_model=Optional[AgentRegistration],
    summary="Update agent registration details",
    tags=["Agents"],
)
async def update_agent_registration_endpoint(
    agent_id: str, payload: AgentRegistrationUpdatePayload
) -> Optional[AgentRegistration]:
    registry = get_registry()
    # Convert Pydantic model to dict, excluding unset fields to ensure partial updates
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No update fields provided.")

    updated_registration = await registry.update_registration(agent_id, updates)
    if not updated_registration:
        # Check if agent exists, update_registration returns None if agent_id not found
        existing_reg = await registry.get_registration(agent_id)
        if not existing_reg:
            raise HTTPException(
                status_code=404,
                detail=f"Agent with ID {agent_id} not found for update.",
            )
        # If agent exists but update failed for other reasons (less likely with current registry impl)
        raise HTTPException(
            status_code=500, detail=f"Failed to update agent {agent_id}."
        )
    return updated_registration


@router.delete(
    "/agents/{agent_id}",
    status_code=200,
    summary="Unregister an agent",
    tags=["Agents"],
)
async def unregister_agent_endpoint(agent_id: str) -> Dict[str, Any]:
    registry = get_registry()
    try:
        success = await registry.unregister(agent_id)
        if success:
            return {"message": "Agent unregistered successfully", "agent_id": agent_id}
        else:
            # Check if agent was not found in the first place
            existing_reg = await registry.get_registration(agent_id)
            if not existing_reg:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent with ID {agent_id} not found for unregistration.",
                )
            raise HTTPException(
                status_code=400,
                detail="Agent unregistration failed for an unknown reason.",
            )
    except Exception as e:
        logger.error("Error unregistering agent agent_id=%s", agent_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/agents/search/semantic",
    response_model=AgentSearchOutput,
    summary="Search agents by semantic capability",
    tags=["Agent Search"],
)
async def search_agents_semantic_endpoint(
    search_input: AgentSearchInput,
) -> AgentSearchOutput:
    registry = get_registry()
    try:
        found_tuples = await registry.get_by_capability_semantic(
            capability_description=search_input.query,
            limit=search_input.top_k
            * 2,  # Fetch more to allow for filtering (e.g. HUMAN type)
            similarity_threshold=search_input.strictness,
            filters=(
                {"tags": search_input.include_tags}
                if search_input.include_tags
                else None
            ),
        )

        # Use the registry search utility function
        results_items = []
        for reg, score in found_tuples:
            if reg.agent_type == AgentType.HUMAN:  # Filter out HUMAN agents
                continue
            item = populate_search_result_item(reg, score, search_input.output_detail)
            results_items.append(item)
            if (
                len(results_items) >= search_input.top_k
            ):  # Apply top_k limit after filtering
                break

        if not results_items:
            return AgentSearchOutput(
                message=f"No agents found matching your query '{search_input.query}' with specified criteria.",
                results=[],
            )

        return AgentSearchOutput(
            message=f"Successfully found {len(results_items)} agents matching your criteria.",
            results=results_items,
        )
    except Exception as e:
        logger.error("Error in semantic search", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error searching for agents: {str(e)}"
        )


@router.get(
    "/agents/search/capability-exact",
    response_model=List[AgentRegistration],
    summary="Search agents by exact capability name",
    tags=["Agent Search"],
)
async def search_agents_by_capability_exact_endpoint(
    capability_name: str = Query(
        ..., description="Exact name of the capability to search for."
    ),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of results to return."
    ),
    similarity_threshold: float = Query(
        0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity for semantic fallback (if applicable in registry method).",
    ),  # Kept for consistency with registry method
) -> List[AgentRegistration]:
    registry = get_registry()
    try:
        return await registry.get_by_capability(
            capability_name=capability_name,
            limit=limit,
            similarity_threshold=similarity_threshold,
        )
    except Exception as e:
        logger.error(
            "Error searching by exact capability name capability=%s",
            capability_name,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Error searching by exact capability: {str(e)}"
        )


@router.get(
    "/capabilities",
    response_model=List[str],
    summary="Get all unique capability names",
    tags=["Capabilities"],
)
async def get_all_capabilities_endpoint() -> List[str]:
    registry = get_registry()
    try:
        return await registry.get_all_capabilities()
    except Exception as e:
        logger.error("Error getting all capabilities", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error getting all capabilities: {str(e)}"
        )


@router.get(
    "/agents/interaction-mode/{mode}",
    response_model=List[AgentRegistration],
    summary="Find agents by interaction mode",
    tags=["Agent Properties"],
)
async def get_agents_by_interaction_mode_endpoint(
    mode: InteractionMode,
) -> List[AgentRegistration]:
    registry = get_registry()
    try:
        # Ensure the mode is a valid InteractionMode enum member if it comes as a string
        # FastAPI should handle this with Pydantic type hint, but good to be aware
        return await registry.get_by_interaction_mode(mode)
    except ValueError:  # If mode string is not a valid InteractionMode
        raise HTTPException(status_code=400, detail=f"Invalid interaction mode: {mode}")
    except Exception as e:
        logger.error(
            "Error getting agents by interaction mode mode=%s", mode, exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error getting agents by interaction mode: {str(e)}",
        )


@router.get(
    "/agents/organization/{organization_name}",
    response_model=List[AgentRegistration],
    summary="Find agents by organization",
    tags=["Agent Properties"],
)
async def get_agents_by_organization_endpoint(
    organization_name: str,
) -> List[AgentRegistration]:
    registry = get_registry()
    try:
        return await registry.get_by_organization(organization_name)
    except Exception as e:
        logger.error(
            "Error getting agents by organization org=%s",
            organization_name,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Error getting agents by organization: {str(e)}"
        )


@router.post(
    "/agents/{agent_id}/verify",
    response_model=bool,
    summary="Verify an agent's identity (triggers verification process)",
    tags=["Agents"],
)
async def verify_agent_endpoint(agent_id: str) -> bool:
    registry = get_registry()
    # First, check if agent exists
    agent_reg = await registry.get_registration(agent_id)
    if not agent_reg:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID {agent_id} not found."
        )
    try:
        # This assumes verify_agent internally updates the registration's verification_status
        # and returns True/False based on the outcome of verify_agent_identity.
        return await registry.verify_agent(agent_id)
    except (
        Exception
    ) as e:  # Catch any other unexpected errors from the verification process
        logger.error("Error verifying agent agent_id=%s", agent_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error verifying agent: {str(e)}")


@router.get(
    "/agents/owner/{owner_id}",
    response_model=List[AgentRegistration],
    summary="Find agents by owner (developer)",
    tags=["Agent Properties"],
)
async def get_agents_by_owner_endpoint(owner_id: str) -> List[AgentRegistration]:
    registry = get_registry()
    try:
        # The registry method get_by_owner uses the 'developer' field
        return await registry.get_by_owner(owner_id)
    except Exception as e:
        logger.error("Error getting agents by owner owner=%s", owner_id, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error getting agents by owner: {str(e)}"
        )


@router.get(
    "/agents/{agent_id}/verify-owner/{owner_id}",
    response_model=bool,
    summary="Verify if a user owns an agent (developer)",
    tags=["Agents"],
)
async def verify_agent_owner_endpoint(agent_id: str, owner_id: str) -> bool:
    registry = get_registry()
    # First, check if agent exists
    agent_reg = await registry.get_registration(agent_id)
    if not agent_reg:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID {agent_id} not found."
        )
    try:
        # The registry method verify_owner uses the 'developer' field against owner_id
        return await registry.verify_owner(agent_id, owner_id)
    except Exception as e:
        logger.error(
            "Error verifying agent owner for agent_id=%s owner=%s",
            agent_id,
            owner_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Error verifying agent owner: {str(e)}"
        )


# Create module-level app (e.g., uvicorn agentconnect.servers.registry_api_server:app)
app = create_registry_api_app()


# Example: How to run this server (e.g., using uvicorn)
# uvicorn agentconnect.servers.registry_api_server:app --reload --port 8000
#
if __name__ == "__main__":
    import uvicorn

    # This allows running directly with `python -m agentconnect.servers.registry_api_server`
    # Using standalone server settings from environment variables
    _settings = RegistryAPISettings()
    _app = create_registry_api_app(_settings)
    uvicorn.run(
        _app,
        host=_settings.host,
        port=_settings.port,
        reload=_settings.reload,
        log_level=_settings.log_level.lower(),
    )
