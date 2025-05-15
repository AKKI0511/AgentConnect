import asyncio
import logging
from typing import Optional

from langchain_core.tools.structured import StructuredTool
from pydantic import BaseModel, Field

from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry

logger = logging.getLogger(__name__)

# --- Input/Output schemas for check collaboration result tool ---


class CheckCollaborationResultInput(BaseModel):
    """Input schema for checking collaboration results."""

    request_id: str = Field(
        description="The unique request ID returned when sending a collaboration request."
    )


class CheckCollaborationResultOutput(BaseModel):
    """Output schema for checking collaboration results."""

    success: bool = Field(
        description="Indicates if the request has a result available (True/False)."
    )
    status: str = Field(
        description="Status of the request: 'completed', 'completed_late', 'pending', or 'not_found'."
    )
    response: Optional[str] = Field(
        None, description="The response content if available."
    )

    def __str__(self) -> str:
        """Return a clean JSON string representation."""
        return self.model_dump_json(indent=2, exclude_none=True)


# --- Implementation of check collaboration result tool ---


def create_check_collaboration_result_tool(
    communication_hub: Optional[CommunicationHub] = None,
    agent_registry: Optional[
        AgentRegistry
    ] = None,  # Kept for potential future standalone enhancements or consistency
    current_agent_id: Optional[
        str
    ] = None,  # Kept for consistency, though not used in current logic
) -> StructuredTool:
    """
    Create a tool for checking the status of previously sent collaboration requests.

    This tool is particularly useful for retrieving late responses that arrived
    after a timeout occurred in the original collaboration request.

    Args:
        communication_hub: Hub for agent communication
        agent_registry: Registry for accessing agent information
        current_agent_id: ID of the agent using the tool

    Returns:
        A StructuredTool for checking collaboration results
    """
    # Determine if we're in standalone mode
    standalone_mode = (
        communication_hub is None
    )  # Simplified standalone check as agent_registry isn't strictly needed for current logic

    # Common description base
    base_description = "Check if a previous collaboration request has completed and retrieve its result."

    if standalone_mode:
        # Standalone mode implementation
        def check_result_standalone(request_id: str) -> CheckCollaborationResultOutput:
            """Standalone implementation that explains limitations."""
            return CheckCollaborationResultOutput(
                success=False,
                status="not_available",
                response=(
                    f"Checking collaboration result for request '{request_id}' is not available in standalone mode. "
                    "This agent is running without a connection to the communication hub. "
                    "Please continue with your own internal capabilities."
                ),
            )

        description = f"[STANDALONE MODE] {base_description} Note: In standalone mode, this tool will explain why checking results isn't available."

        return StructuredTool.from_function(
            func=check_result_standalone,
            name="check_collaboration_result",
            description=description,
            args_schema=CheckCollaborationResultInput,
            return_direct=False,
            metadata={"category": "collaboration"},
        )

    # Connected mode implementation
    async def check_result_async(request_id: str) -> CheckCollaborationResultOutput:
        """Check if a previous collaboration request has a result asynchronously."""
        if (
            communication_hub is None
        ):  # Should not happen if not in standalone mode, but defensive check
            return CheckCollaborationResultOutput(
                success=False,
                status="error",
                response="Communication hub not available.",
            )

        # Check for late responses first
        if (
            hasattr(communication_hub, "late_responses")
            and request_id in communication_hub.late_responses
        ):
            logger.debug(f"Found late response for request {request_id}")
            # Assuming late_responses stores the actual response content or a message object with content
            response_obj = communication_hub.late_responses.pop(
                request_id
            )  # Pop to consume it
            response_content = getattr(response_obj, "content", str(response_obj))
            return CheckCollaborationResultOutput(
                success=True,
                status="completed_late",
                response=response_content,
            )

        # Check pending responses (futures)
        if (
            hasattr(communication_hub, "pending_responses")
            and request_id in communication_hub.pending_responses
        ):
            future = communication_hub.pending_responses[request_id]
            if future.done():
                # Check if it was a timeout previously marked
                if hasattr(future, "_timed_out") and future._timed_out:
                    logger.debug(
                        f"Request {request_id} previously timed out and is still pending final result."
                    )
                    # It's done but was a timeout, so it might not have a "real" result yet for this check.
                    # Or, if it completed *after* timeout but *before* late_responses check, it might be here.
                    # For simplicity, if it timed out, we expect it via late_responses primarily.
                    # This path might mean it completed but the result wasn't moved to late_responses correctly, or it's an error state.
                    # To be safe, we'll treat it as still pending if it was marked as timed_out.
                    # However, if it has a result, it means it completed after timeout. This could be a race condition.
                    try:
                        response_obj = future.result(
                            timeout=0
                        )  # Non-blocking get result
                        response_content = getattr(
                            response_obj, "content", str(response_obj)
                        )
                        logger.debug(
                            f"Found completed (previously timed out) response for request {request_id}"
                        )
                        # Once retrieved, remove from pending_responses to avoid re-processing.
                        del communication_hub.pending_responses[request_id]
                        return CheckCollaborationResultOutput(
                            success=True,
                            status="completed_late",  # Technically completed after initial timeout observation
                            response=response_content,
                        )
                    except asyncio.TimeoutError:
                        return CheckCollaborationResultOutput(
                            success=False,
                            status="pending_after_timeout",
                            response=f"Request {request_id} previously timed out and is awaiting late response.",
                        )
                    except Exception as e:  # Other errors getting result
                        logger.error(
                            f"Error getting result from future for {request_id} (previously timed_out): {str(e)}"
                        )
                        del communication_hub.pending_responses[request_id]
                        return CheckCollaborationResultOutput(
                            success=False,
                            status="error",
                            response=f"Error retrieving response for {request_id}: {str(e)}",
                        )
                else:  # Not marked as timed_out and is done
                    try:
                        logger.debug(
                            f"Found completed (non-timeout) response for request {request_id}"
                        )
                        response_obj = future.result(
                            timeout=0
                        )  # Non-blocking get result
                        response_content = getattr(
                            response_obj, "content", str(response_obj)
                        )
                        # Once retrieved, remove from pending_responses.
                        del communication_hub.pending_responses[request_id]
                        return CheckCollaborationResultOutput(
                            success=True,
                            status="completed",
                            response=response_content,
                        )
                    except (
                        asyncio.TimeoutError
                    ):  # Should not happen if future.done() is true and not timed_out
                        logger.warning(
                            f"Future for {request_id} was done but result call timed out. Treating as pending."
                        )
                        return CheckCollaborationResultOutput(
                            success=False,
                            status="pending",
                            response=f"Request {request_id} processing result.",
                        )
                    except Exception as e:
                        logger.error(
                            f"Error getting result from future for {request_id}: {str(e)}"
                        )
                        if (
                            request_id in communication_hub.pending_responses
                        ):  # Attempt to remove if still there
                            del communication_hub.pending_responses[request_id]
                        return CheckCollaborationResultOutput(
                            success=False,
                            status="error",
                            response=f"Error retrieving response for {request_id}: {str(e)}",
                        )
            else:
                # Still pending and not timed out previously
                return CheckCollaborationResultOutput(
                    success=False,
                    status="pending",
                    response="The collaboration request is still being processed. Try checking again later.",
                )

        # Request ID not found in late_responses or pending_responses
        logger.warning(
            f"No result or pending task found for request ID: {request_id}. It might have completed and been cleared, never existed, or an issue occurred."
        )
        return CheckCollaborationResultOutput(
            success=False,
            status="not_found",
            response=f"No active or late result found for request ID: {request_id}. The request may have been completed and cleared, the ID may be incorrect, or it was never registered.",
        )

    # Synchronous wrapper
    def check_result(request_id: str) -> CheckCollaborationResultOutput:
        """Check if a previous collaboration request has a result."""
        try:
            if asyncio.get_event_loop().is_running():
                future = asyncio.run_coroutine_threadsafe(
                    check_result_async(request_id), asyncio.get_event_loop()
                )
                return future.result()
            else:
                return asyncio.run(check_result_async(request_id))
        except RuntimeError:
            logger.error(
                f"RuntimeError in check_result sync wrapper for {request_id}. Attempting new loop."
            )
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(check_result_async(request_id))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(
                f"Error in check_result sync wrapper for {request_id}: {str(e)}"
            )
            return CheckCollaborationResultOutput(
                success=False,
                status="error",
                response=f"Error checking result via sync wrapper: {str(e)}",
            )

    # Create and return the connected mode tool
    description = f"{base_description} This is useful for retrieving responses that arrived after the initial timeout period."

    return StructuredTool.from_function(
        func=check_result,
        name="check_collaboration_result",
        description=description,
        args_schema=CheckCollaborationResultInput,
        return_direct=False,
        handle_tool_error=True,
        coroutine=check_result_async,
        metadata={"category": "collaboration"},
    )
