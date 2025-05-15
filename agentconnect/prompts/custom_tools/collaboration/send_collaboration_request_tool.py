import asyncio
import logging
import uuid
import json  # For potential use if response is complex
from typing import Optional, Any  # Added Any, Dict for kwargs flexibility

from langchain_core.tools.structured import StructuredTool
from pydantic import BaseModel, Field

from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import AgentType

logger = logging.getLogger(__name__)

# --- Input/Output schemas for send collaboration request tool ---


class SendCollaborationRequestInput(BaseModel):
    """Input schema for sending a collaboration request."""

    target_agent_id: str = Field(
        description="The exact `agent_id` (obtained from `search_for_agents` output) of the agent you want to delegate the task to."
    )
    task: str = Field(
        description="A clear and detailed description of the task, providing ALL necessary context for the collaborating agent to understand and execute the request."
    )
    timeout: int = Field(
        default=120,
        description="Maximum seconds to wait for the collaborating agent's response (default 120).",
    )

    class Config:
        """Config for the SendCollaborationRequestInput."""

        extra = "allow"  # Allow additional fields to be passed as kwargs


class SendCollaborationRequestOutput(BaseModel):
    """Output schema for sending a collaboration request."""

    success: bool = Field(
        description="Indicates if the request was successfully SENT (True/False). Does NOT guarantee the collaborator completed the task."
    )
    response: Optional[str] = Field(
        None,
        description="The direct message content received back from the collaborating agent. Analyze this response carefully to determine the next step (e.g., pay, provide more info, present to user).",
    )
    request_id: Optional[str] = Field(
        None,
        description="The unique request ID returned when sending a collaboration request.",
    )
    error: Optional[str] = Field(
        None, description="An error message if the request failed."
    )

    def __str__(self) -> str:
        """Return a clean JSON string representation."""
        return self.model_dump_json(indent=2, exclude_none=True)


# --- Implementation of send collaboration request tool ---


def create_send_collaboration_request_tool(
    communication_hub: Optional[CommunicationHub] = None,
    agent_registry: Optional[AgentRegistry] = None,
    current_agent_id: Optional[str] = None,
) -> StructuredTool:
    """
    Create a tool for sending collaboration requests to other agents.

    Args:
        communication_hub: Hub for agent communication
        agent_registry: Registry for accessing agent information
        current_agent_id: ID of the agent using the tool

    Returns:
        A StructuredTool for sending collaboration requests
    """
    # Determine if we're in standalone mode
    standalone_mode = (
        communication_hub is None or agent_registry is None or not current_agent_id
    )

    # Common description base
    base_description = (
        "Delegates a specific task to another agent identified by `search_for_agents`."
    )

    if standalone_mode:
        # Standalone mode implementation
        def send_request_standalone(
            target_agent_id: str, task: str, timeout: int = 30, **kwargs: Any
        ) -> SendCollaborationRequestOutput:
            """Standalone implementation that explains limitations."""
            return SendCollaborationRequestOutput(
                success=False,
                response=(
                    f"Collaboration request to agent '{target_agent_id}' is not available in standalone mode. "
                    "This agent is running without a connection to other agents. "
                    "Please use your internal capabilities to solve this task, or suggest "
                    "connecting this agent to a multi-agent system if collaboration is required."
                ),
                request_id=None,
            )

        description = f"[STANDALONE MODE] {base_description} Note: In standalone mode, this tool will explain why collaboration isn't available."

        return StructuredTool.from_function(
            func=send_request_standalone,
            name="send_collaboration_request",
            description=description,
            args_schema=SendCollaborationRequestInput,
            return_direct=False,
            handle_tool_error=True,
            metadata={"category": "collaboration"},
        )

    # Connected mode implementation
    # Store the agent ID at creation time
    creator_agent_id = current_agent_id
    logger.debug(f"Creating collaboration request tool for agent: {creator_agent_id}")

    async def send_request_async(
        target_agent_id: str, task: str, timeout: int = 120, **kwargs: Any
    ) -> SendCollaborationRequestOutput:
        """Send a collaboration request to another agent asynchronously."""
        sender_id = creator_agent_id  # Use the agent ID captured at tool creation

        if sender_id is None:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: current_agent_id was not provided when creating the tool.",
                error="configuration_error",
            )

        # Validate request parameters
        if sender_id == target_agent_id:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Cannot send request to yourself.",
                error="self_request_error",
            )

        if not await communication_hub.is_agent_active(target_agent_id):
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Agent {target_agent_id} not found or not active.",
                error="target_agent_not_found",
            )

        # Ensure agent_registry is not None before using it
        if agent_registry is None:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Agent registry not available for type check.",
                error="registry_not_available",
            )

        if await agent_registry.get_agent_type(target_agent_id) == AgentType.HUMAN:
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Cannot send requests to human agents.",
                error="target_is_human_error",
            )

        # Prepare collaboration metadata
        metadata = kwargs.copy() if kwargs else {}

        # Add collaboration chain tracking to prevent loops
        if "collaboration_chain" not in metadata:
            metadata["collaboration_chain"] = []

        # Ensure collaboration_chain is a list before appending
        if not isinstance(metadata["collaboration_chain"], list):
            metadata["collaboration_chain"] = []  # Reset if not a list

        if sender_id not in metadata["collaboration_chain"]:
            metadata["collaboration_chain"].append(sender_id)

        if target_agent_id in metadata["collaboration_chain"]:
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Detected loop in collaboration chain with {target_agent_id}. Chain: {metadata['collaboration_chain']}",
                error="collaboration_loop_detected",
            )

        # If this is the first agent in the chain, store the original sender
        if len(metadata["collaboration_chain"]) == 1:
            metadata["original_sender"] = metadata["collaboration_chain"][0]

        # Prevent sending to original sender
        if (
            "original_sender" in metadata
            and metadata["original_sender"] == target_agent_id
        ):
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Cannot send request back to original sender {target_agent_id}.",
                error="cannot_send_to_original_sender",
            )

        # Limit collaboration chain length
        if len(metadata["collaboration_chain"]) > 5:  # Max 5 hops
            return SendCollaborationRequestOutput(
                success=False,
                response="Error: Collaboration chain too long (max 5 hops). Simplify request.",
                error="collaboration_chain_too_long",
            )

        try:
            # Calculate appropriate timeout
            adjusted_timeout = min(timeout or 120, 300)  # Cap at 5 minutes

            # Generate a unique request ID if not provided
            request_id = metadata.get("request_id", str(uuid.uuid4()))
            metadata["request_id"] = request_id

            # Send the request and wait for response
            logger.debug(
                f"Sending collaboration from {sender_id} to {target_agent_id} with request_id: {request_id}"
            )
            response_content = await communication_hub.send_collaboration_request(
                sender_id=sender_id,
                receiver_id=target_agent_id,
                task_description=task,
                timeout=adjusted_timeout,
                **metadata,  # Pass all other kwargs as metadata
            )

            # --- Handle potential non-string/list response from LLM --- START
            cleaned_response_content = response_content
            if not isinstance(response_content, str) and response_content is not None:
                if (
                    isinstance(response_content, list)
                    and len(response_content) == 1
                    and isinstance(response_content[0], str)
                ):
                    # Handle the specific case of ['string']
                    logger.warning(
                        f"Received list-wrapped response from {target_agent_id} for request {request_id}, extracting string."
                    )
                    cleaned_response_content = response_content[0]
                else:
                    # For any other non-string type (dict, multi-list, int, etc.), convert to JSON string
                    try:
                        logger.warning(
                            f"Received non-string response type {type(response_content).__name__} from {target_agent_id} for request {request_id}, converting to JSON string."
                        )
                        cleaned_response_content = json.dumps(
                            response_content
                        )  # Attempt JSON conversion
                    except TypeError as e:
                        # Fallback if JSON conversion fails (e.g., complex object)
                        logger.error(
                            f"Could not JSON serialize response type {type(response_content).__name__} for request {request_id}: {e}. Using str() representation."
                        )
                        cleaned_response_content = str(response_content)
            # --- Handle potential non-string/list response from LLM --- END

            # Handle timeout case (response_content is None or contains timeout indicator)
            if cleaned_response_content is None or (
                isinstance(cleaned_response_content, str)
                and "No immediate response received"
                in cleaned_response_content  # Specific check for timeout from hub
            ):
                logger.warning(f"Timeout on request {request_id} to {target_agent_id}")
                return SendCollaborationRequestOutput(
                    success=False,  # Technically request was sent, but no immediate reply implies a form of failure for this sync-feeling call
                    response=f"No immediate response from {target_agent_id} within {adjusted_timeout} seconds. "
                    f"The request is still processing (ID: {request_id}). "
                    f"Check for a late response using check_collaboration_result with this request ID.",
                    error="timeout",
                    request_id=request_id,
                )

            # Handle success case
            logger.debug(
                f"Got response from {target_agent_id} for request {request_id}"
            )
            return SendCollaborationRequestOutput(
                success=True, response=cleaned_response_content, request_id=request_id
            )

        except Exception as e:
            logger.exception(
                f"Error sending collaboration request {request_id} from {sender_id} to {target_agent_id}: {str(e)}"
            )
            # Attempt to generate a request_id if not already set for error reporting
            final_request_id = metadata.get("request_id") if metadata else None
            if (
                not final_request_id and "request_id" in locals()
            ):  # if it was generated inside try
                final_request_id = request_id

            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error: Collaboration failed - {str(e)}",
                error="collaboration_exception",
                request_id=final_request_id,  # Include request_id if available
            )

    # Synchronous wrapper
    def send_request(
        target_agent_id: str,
        task: str,
        timeout: int = 30,
        **kwargs: Any,  # timeout default from original was 30
    ) -> SendCollaborationRequestOutput:
        """Send a collaboration request to another agent."""
        try:
            # Ensure we are in an event loop to run async code
            if asyncio.get_event_loop().is_running():
                future = asyncio.run_coroutine_threadsafe(
                    send_request_async(target_agent_id, task, timeout, **kwargs),
                    asyncio.get_event_loop(),
                )
                return future.result()  # Wait for the result from the other thread
            else:
                return asyncio.run(
                    send_request_async(target_agent_id, task, timeout, **kwargs)
                )
        except RuntimeError as e:
            # Handle cases where asyncio.run might fail if called from a running loop
            # or if a new loop can't be started.
            logger.error(
                f"RuntimeError in send_request sync wrapper: {str(e)}. Attempting new loop."
            )
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(
                    send_request_async(target_agent_id, task, timeout, **kwargs)
                )
            finally:
                loop.close()
                asyncio.set_event_loop(None)  # Clean up loop association
        except Exception as e:
            logger.error(f"Error in send_request sync wrapper: {str(e)}")
            return SendCollaborationRequestOutput(
                success=False,
                response=f"Error sending collaboration request via sync wrapper: {str(e)}",
                error="sync_wrapper_exception",
            )

    # Create and return the connected mode tool
    description = (
        f"{base_description} Sends your request and waits for the collaborator's response. "
        "Use this tool ONLY to initiate a new collaboration request to another agent. "
        "When you receive a collaboration request, reply directly to the requesting agent with your result, clarification, or error—do NOT use this tool to reply to the same agent. "
        "The response might be the final result, a request for payment, or a request for clarification, requiring further action from you."
    )

    return StructuredTool.from_function(
        func=send_request,
        name="send_collaboration_request",
        description=description,
        args_schema=SendCollaborationRequestInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=send_request_async,  # Retain async version for StructuredTool
        metadata={"category": "collaboration"},
    )
