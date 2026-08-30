"""
Registry Client for AgentConnect

This client provides a high-level interface for interacting with the AgentConnect Registry API Server.
It mimics the interface of agentconnect.index.registry.AgentRegistry, but uses HTTPX for asynchronous requests.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from functools import wraps
import time

import httpx
from pydantic import ValidationError

from agentconnect.index.registry.registration import AgentRegistration
from agentconnect.index.registry.search import (
    AgentSearchInput,
    AgentSearchOutput,
    AgentSearchResultItem,
)
from agentconnect.core.types import AgentType, InteractionMode

logger = logging.getLogger(__name__)


class _RegistryClientDefaults:
    base_url = "http://localhost:8000"
    default_timeout = 30.0
    connect_timeout = 10.0
    read_timeout = 30.0
    pool_timeout = 5.0
    max_retries = 3
    retry_backoff_factor = 0.5
    retryable_status_codes = [502, 503, 504]
    max_connections = 10
    max_keepalive_connections = 5


def with_retry(
    max_retries: Optional[int] = None,
    retry_backoff_factor: Optional[float] = None,
    retryable_status_codes: Optional[List[int]] = None,
):
    """Decorator to add exponential backoff retry logic to async methods."""

    def decorator(func):
        """Decorator to add exponential backoff retry logic to async methods."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            """Wrapper function with retry logic."""
            # Get configuration from settings if not provided
            client_settings = _RegistryClientDefaults

            actual_max_retries = (
                max_retries if max_retries is not None else client_settings.max_retries
            )
            actual_backoff_factor = (
                retry_backoff_factor
                if retry_backoff_factor is not None
                else client_settings.retry_backoff_factor
            )
            actual_retryable_codes = (
                set(retryable_status_codes)
                if retryable_status_codes is not None
                else set(client_settings.retryable_status_codes)
            )

            if actual_max_retries < 0:
                raise ValueError("max_retries must be >= 0")

            last_exception = None

            for attempt in range(actual_max_retries + 1):  # 0 to max_retries
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    # Check if status code is retryable
                    if e.response.status_code not in actual_retryable_codes:
                        raise e
                    last_exception = e
                    if attempt == actual_max_retries:
                        break

                    wait_time = actual_backoff_factor * (2**attempt)
                    logger.warning(
                        "Transient HTTP %s attempt=%s/%s backoff=%ss",
                        e.response.status_code,
                        attempt + 1,
                        actual_max_retries + 1,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                except httpx.RequestError as e:
                    last_exception = e
                    if attempt == actual_max_retries:
                        break

                    wait_time = actual_backoff_factor * (2**attempt)
                    logger.warning(
                        "Network error attempt=%s/%s backoff=%ss",
                        attempt + 1,
                        actual_max_retries + 1,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    # Don't retry non-network errors
                    raise e

            # Re-raise the last exception if all retries failed
            raise last_exception

        return wrapper

    return decorator


class RegistryAPIClient:
    """
    Client for interacting with the AgentConnect Registry API Server.
    This client mimics the interface of `agentconnect.index.registry.AgentRegistry`.

    Quickstart Example:
        .. code-block:: python

            import asyncio
            from agentconnect.index import RegistryAPIClient

            async def main():
                async with RegistryAPIClient() as client:
                    # Get all registered agents
                    agents = await client.get_all_agents()
                    print(f"Found {len(agents)} agents")

                    # Search for agents by capability
                    results = await client.get_by_capability_semantic(
                        capability_description="data analysis",
                        limit=5
                    )
                    for agent, score in results:
                        print(f"{agent.name}: {score:.3f}")

            asyncio.run(main())
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        pool_timeout: Optional[float] = None,
        max_connections: Optional[int] = None,
        max_keepalive_connections: Optional[int] = None,
    ):
        """
        Initialize the API client.

        All None values use the Index client defaults.

        Args:
            base_url: The base URL of the `AgentRegistry` API server.
            timeout: Default timeout for HTTP requests in seconds.
            connect_timeout: Timeout for establishing connections in seconds.
            read_timeout: Timeout for reading responses in seconds.
            pool_timeout: Timeout for acquiring connection from pool in seconds.
            max_connections: Maximum number of connections in the pool.
            max_keepalive_connections: Maximum number of keep-alive connections.
        """
        client_settings = _RegistryClientDefaults

        # Resolve base URL from args or settings; raise clear error if missing
        resolved_base_url = (
            base_url if base_url is not None else client_settings.base_url
        )
        if not resolved_base_url:
            raise ValueError(
                "RegistryAPIClient base_url is not configured. Pass base_url explicitly."
            )
        self.base_url = (
            resolved_base_url
            if resolved_base_url.endswith("/")
            else f"{resolved_base_url}/"
        )

        # Create timeout configuration
        timeout_config = httpx.Timeout(
            timeout=timeout if timeout is not None else client_settings.default_timeout,
            connect=(
                connect_timeout
                if connect_timeout is not None
                else client_settings.connect_timeout
            ),
            read=(
                read_timeout
                if read_timeout is not None
                else client_settings.read_timeout
            ),
            pool=(
                pool_timeout
                if pool_timeout is not None
                else client_settings.pool_timeout
            ),
        )

        # Create limits configuration for connection pooling
        limits = httpx.Limits(
            max_connections=(
                max_connections
                if max_connections is not None
                else client_settings.max_connections
            ),
            max_keepalive_connections=(
                max_keepalive_connections
                if max_keepalive_connections is not None
                else client_settings.max_keepalive_connections
            ),
        )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_config,
            limits=limits,
            headers={
                "User-Agent": "AgentConnect-Registry-Client/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        self._initialized_event = asyncio.Event()
        self._initialized_event.set()  # Client is "initialized" upon instantiation

    async def close(self):
        """Closes the underlying HTTPX client. Should be called on cleanup."""
        await self._client.aclose()

    @with_retry()
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        expected_status: int = 200,
        response_model: Optional[Type[Any]] = None,
    ) -> Optional[Any]:
        """Helper method to make HTTP requests with retry logic."""
        try:
            start_time = time.time()
            response = await self._client.request(
                method, endpoint, params=params, json=json_data
            )
            request_duration = time.time() - start_time

            logger.debug(
                "%s %s status=%s duration_ms=%d",
                method,
                endpoint,
                response.status_code,
                int(request_duration * 1000.0),
            )

            if response.status_code == expected_status:
                if response_model:
                    try:
                        # Handle cases where response content might be empty for 200/201 on success (e.g. delete)
                        if not response.content and (
                            expected_status == 200
                            or expected_status == 201
                            or expected_status == 204
                        ):  # 204 No Content
                            # For DELETE or successful updates that don't return body, but we expect a model that might be a simple bool/dict
                            if response_model == bool:
                                return True
                            if response_model == dict:
                                return {}  # common for success messages
                            return None  # Or handle as per specific endpoint needs

                        return (
                            response_model(**response.json())
                            if not isinstance(response.json(), list)
                            else [response_model(**item) for item in response.json()]
                        )
                    except ValidationError as e:
                        logger.error(
                            "Validation error for %s %s: %s",
                            method,
                            endpoint,
                            e.json(),
                        )
                        return None
                    except (
                        Exception
                    ) as e:  # Catch broader JSON parsing errors or other issues
                        logger.error(
                            "Error parsing response for %s %s: %s - %s",
                            method,
                            endpoint,
                            response.text,
                            e,
                        )
                        return None
                elif expected_status == 204:  # No content expected
                    return True
                return response.json()  # Return raw JSON if no model specified

            elif response.status_code == 404:
                logger.debug("%s %s status=404", method, endpoint)
                return None  # Mimic AgentRegistry behavior (e.g. get_registration returns None)

            # Raise HTTPStatusError for all other error codes - let retry decorator handle retryable ones
            response.raise_for_status()

        except Exception:
            logger.error(
                "Unexpected error in _request method=%s endpoint=%s",
                method,
                endpoint,
                exc_info=True,
            )
            return None

    async def ensure_initialized(self):
        """Mimics AgentRegistry's ensure_initialized. For the client, this is a no-op."""
        await self._initialized_event.wait()
        # Optionally, could add a ping to a server health endpoint here if one exists.
        return

    async def register(self, registration: AgentRegistration) -> bool:
        """Register a new agent."""
        payload = registration.model_dump(mode="json")
        response_data = await self._request(
            "POST", "agents/register", json_data=payload, expected_status=201
        )
        return response_data is not None and "agent_id" in response_data

    async def unregister(self, agent_id: str) -> bool:
        """Remove agent from registry."""
        response_data = await self._request(
            "DELETE", f"agents/{agent_id}", expected_status=200
        )  # Server returns 200 with a message
        return response_data is not None and "agent_id" in response_data

    async def get_registration(self, agent_id: str) -> Optional[AgentRegistration]:
        """Get agent registration details."""
        return await self._request(
            "GET", f"agents/{agent_id}", response_model=AgentRegistration
        )

    async def get_all_agents(self) -> List[AgentRegistration]:
        """Get a list of all agents registered in the system."""
        results = await self._request("GET", "agents", response_model=AgentRegistration)
        return results if results else []

    async def update_registration(
        self, agent_id: str, updates: Dict[str, Any]
    ) -> Optional[AgentRegistration]:
        """Update agent registration details."""
        # The server expects AgentRegistrationUpdatePayload.
        # We construct it from the 'updates' dict. FastAPI will validate.
        # No need to instantiate AgentRegistrationUpdatePayload here if just passing dict.
        return await self._request(
            "PUT",
            f"agents/{agent_id}",
            json_data=updates,
            response_model=AgentRegistration,
        )

    async def get_by_capability_semantic(
        self,
        capability_description: str,
        limit: int = 10,
        similarity_threshold: float = 0.1,
        filters: Optional[Dict[str, List[str]]] = None,
    ) -> List[Tuple[AgentRegistration, float]]:
        """Find agents by capability description using semantic search."""
        search_input = AgentSearchInput(
            query=capability_description,
            top_k=limit,  # Server side will fetch top_k*2 then filter, client asks for final top_k
            strictness=similarity_threshold,
            include_tags=filters.get("tags") if filters else None,
            output_detail="full",  # Request full detail to reconstruct AgentRegistration
        )

        search_output_data = await self._request(
            "POST",
            "agents/search/semantic",
            json_data=search_input.model_dump(),
            response_model=AgentSearchOutput,
        )

        if not search_output_data or not hasattr(search_output_data, "results"):
            return []

        # search_output_data is an AgentSearchOutput instance if parsing was successful
        # Its 'results' attribute is List[AgentSearchResultItem]

        final_results: List[Tuple[AgentRegistration, float]] = []

        # The server's search result (AgentSearchResultItem) is a subset of AgentRegistration.
        # To truly mimic AgentRegistry, we must return full AgentRegistration objects.
        # This requires an additional fetch for each agent_id if AgentSearchResultItem isn't sufficient.
        # With output_detail='full', AgentSearchResultItem is quite comprehensive.
        # Let's try to map directly and note any missing fields or assume 'full' is enough.

        # Reconstructing AgentRegistration from AgentSearchResultItem (output_detail='full')
        # This is an approximation as AgentSearchResultItem might not have all exact nested models
        # like IdentityProfile. It's a "best effort" mimicry without N+1 calls.
        # A more robust (but slower) way would be to call self.get_registration(item.agent_id) for each.
        # For now, we attempt direct mapping from the rich AgentSearchResultItem.

        # **Decision**: The N+1 calls are necessary for data integrity.
        # The API server /agents/{agent_id} provides the definitive AgentRegistration with complete identity info.
        # AgentSearchResultItem lacks critical fields: identity, agent_type, interaction_modes, registered_at

        if not isinstance(search_output_data.results, list):  # Ensure results is a list
            logger.warning(
                "Semantic search returned non-list results: %s",
                search_output_data.results,
            )
            return []

        # Create a list of tasks for fetching full registrations
        result_items_with_scores: List[Tuple[str, float]] = []

        for item_data in search_output_data.results:
            # item_data here is already an AgentSearchResultItem instance due to response_model parsing
            if isinstance(item_data, AgentSearchResultItem):
                result_items_with_scores.append(
                    (item_data.agent_id, item_data.similarity_score)
                )
            else:
                # This case should ideally not happen if Pydantic parsing is correct
                logger.warning(
                    "Skipping unexpected item type in search results: %s",
                    type(item_data),
                )
                continue

        async def fetch_full_reg_with_score(agent_id: str, score: float):
            full_reg = await self.get_registration(agent_id)
            if full_reg:
                return (full_reg, score)
            return None

        # Gather results from fetching full registrations
        # Limit concurrency if necessary, though for 'limit' items it might be fine
        potential_results = await asyncio.gather(
            *(fetch_full_reg_with_score(aid, s) for aid, s in result_items_with_scores)
        )

        for res_tuple in potential_results:
            if res_tuple:
                final_results.append(res_tuple)
                if len(final_results) >= limit:  # Ensure we don't exceed original limit
                    break

        return final_results

    async def get_by_capability(
        self,
        capability_name: str,
        limit: int = 10,
        similarity_threshold: float = 0.1,  # similarity_threshold for API consistency
    ) -> List[AgentRegistration]:
        """Find agents by capability name (exact match)."""
        params = {
            "capability_name": capability_name,
            "limit": limit,
            "similarity_threshold": similarity_threshold,  # Server endpoint has this param
        }
        results = await self._request(
            "GET",
            "agents/search/capability-exact",
            params=params,
            response_model=AgentRegistration,
        )
        return results if results else []

    async def get_all_capabilities(self) -> List[str]:
        """Get a list of all unique capability names registered in the system."""
        # The server returns List[str] directly.
        results = await self._request("GET", "capabilities")
        return results if isinstance(results, list) else []

    async def get_agent_type(self, agent_id: str) -> Optional[AgentType]:
        """Get the type of an agent."""
        registration = await self.get_registration(agent_id)
        if registration:
            return registration.agent_type
        return None

    async def get_by_interaction_mode(
        self, mode: InteractionMode
    ) -> List[AgentRegistration]:
        """Find agents by interaction mode."""
        # FastAPI converts path param 'mode' (string) to InteractionMode enum based on server endpoint type hint.
        results = await self._request(
            "GET",
            f"agents/interaction-mode/{mode.value}",
            response_model=AgentRegistration,
        )
        return results if results else []

    async def get_by_organization(self, organization: str) -> List[AgentRegistration]:
        """Find agents by organization."""
        results = await self._request(
            "GET",
            f"agents/organization/{organization}",
            response_model=AgentRegistration,
        )
        return results if results else []

    async def get_verified_agents(self) -> List[AgentRegistration]:
        """Get all verified agents."""
        results = await self._request(
            "GET", "agents/verified", response_model=AgentRegistration
        )
        return results if results else []

    async def verify_agent(self, agent_id: str) -> bool:
        """Verify an agent's identity (triggers verification process on server)."""
        # Server POST /agents/{agent_id}/verify returns a boolean.
        result = await self._request(
            "POST", f"agents/{agent_id}/verify", expected_status=200
        )
        return isinstance(result, bool) and result  # Ensure it's literally True

    async def get_by_owner(
        self, owner_id: str
    ) -> List[AgentRegistration]:  # owner_id is developer_id
        """Find agents by owner (developer)."""
        results = await self._request(
            "GET", f"agents/owner/{owner_id}", response_model=AgentRegistration
        )
        return results if results else []

    async def verify_owner(
        self, agent_id: str, owner_id: str
    ) -> bool:  # owner_id is developer_id
        """Verify if a user owns an agent (developer)."""
        # Server GET /agents/{agent_id}/verify-owner/{owner_id} returns a boolean.
        result = await self._request(
            "GET", f"agents/{agent_id}/verify-owner/{owner_id}", expected_status=200
        )
        return isinstance(result, bool) and result

    # --- Context manager methods ---
    async def __aenter__(self):
        # self._client is initialized in __init__
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Example Usage (for testing purposes, typically not in the client file itself):
# async def main():
#     client = RegistryAPIClient(base_url="http://localhost:8000") # Assuming server runs on port 8000
#     try:
#         await client.ensure_initialized()
#         print("Client initialized.")

#         all_agents = await client.get_all_agents()
#         print(f"All agents: {len(all_agents)}")
#         if all_agents:
#             print(f"First agent: {all_agents[0].name if all_agents[0] else 'N/A'}")

#         # Test register (requires a valid AgentRegistration object)
#         from agentconnect.core.identity import IdentityProfile, VerificationMethod
#         from agentconnect.core.types import Capability

#         test_reg = AgentRegistration(
#             agent_id="client-test-agent-002",
#             agent_type=AgentType.AI,
#             name="Client Test Bot",
#             summary="A bot registered via API client for testing.",
#             identity=IdentityProfile(
#                 unique_identifier="client-test-agent-002@example.com",
#                 verification_methods=[VerificationMethod.NONE]
#             ),
#             capabilities=[Capability(name="test_capability", description="Can be tested by client")],
#             tags=["test", "client_registered"]
#         )
#         # First, try to unregister if it exists from a previous run
#         unreg_success_prev = await client.unregister(test_reg.agent_id)
#         print(f"Pre-unregistration of {test_reg.agent_id} was successful: {unreg_success_prev}")

#         reg_success = await client.register(test_reg)
#         print(f"Registration of {test_reg.agent_id} successful: {reg_success}")

#         if reg_success:
#             fetched_reg = await client.get_registration(test_reg.agent_id)
#             print(f"Fetched registration for {test_reg.agent_id}: {fetched_reg.name if fetched_reg else 'Not Found'}")

#             semantic_results = await client.get_by_capability_semantic(
#                 capability_description="something that can be tested by client",
#                 limit=2
#             )
#             print(f"Semantic search results for 'tested by client': {len(semantic_results)}")
#             for r, score in semantic_results:
#                 print(f"  - {r.name} (ID: {r.agent_id}), Score: {score:.4f}")


#             unreg_success = await client.unregister(test_reg.agent_id)
#             print(f"Unregistration of {test_reg.agent_id} successful: {unreg_success}")


#     except Exception as e:
#         print(f"An error occurred: {e}")
#     finally:
#         await client.close()

# if __name__ == "__main__":
#     # To run this example, ensure the API server (registry_api_server.py) is running.
#     # E.g., uvicorn agentconnect.index.service:app --reload --port 8000
#     # logging.basicConfig(level=logging.DEBUG) # Enable debug logging for httpx
#     # httpx_logger = logging.getLogger("httpx")
#     # httpx_logger.setLevel(logging.DEBUG)
#     # httpx_logger.addHandler(logging.StreamHandler())

#     asyncio.run(main())
