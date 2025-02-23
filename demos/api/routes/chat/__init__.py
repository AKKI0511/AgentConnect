from contextlib import asynccontextmanager
from fastapi import APIRouter, WebSocket, Depends, BackgroundTasks, Response
from fastapi_limiter.depends import RateLimiter
from fastapi.security import OAuth2PasswordBearer
import asyncio

from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.api_validation import verify_token
from demos.api.models.chat import (
    CreateSessionRequest,
    SessionResponse,
)

from .session import cleanup_inactive_sessions
from .endpoints import (
    websocket_endpoint_handler,
    create_session_handler,
    get_session_handler,
    delete_session_handler,
)
from .providers import get_available_providers

# Track cleanup task
_cleanup_task = None


@asynccontextmanager
async def lifespan(router: APIRouter):
    """Lifespan context manager for chat router"""
    global _cleanup_task
    # Startup
    _cleanup_task = asyncio.create_task(cleanup_inactive_sessions())
    logger.info("Chat router started, cleanup task initialized")
    yield
    # Shutdown
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await asyncio.wait_for(_cleanup_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception as e:
            logger.error(f"Error during cleanup task shutdown: {str(e)}")
        _cleanup_task = None
    logger.info("Chat router shutdown, cleanup task cancelled")


router = APIRouter(lifespan=lifespan)
logger = get_logger("chat_routes")
config = get_config()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat communication between agents"""
    try:
        # Get token from query parameters or headers
        token = None
        if "token" in websocket.query_params:
            token = websocket.query_params["token"]
        elif "authorization" in websocket.headers:
            auth_header = websocket.headers["authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            logger.warning(f"No token provided for session {session_id}")
            await websocket.close(code=4003)
            return

        # Verify token
        try:
            payload = verify_token(token)
            current_user = payload["sub"]
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            await websocket.close(code=4003)
            return

        await websocket_endpoint_handler(websocket, session_id, current_user)
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {str(e)}")
        try:
            await websocket.close(code=4000)
        except Exception as e:
            logger.error(f"Error closing WebSocket: {str(e)}")


@router.post(
    "/sessions/create",
    response_model=SessionResponse,
    summary="Create new agent session",
    description="Create a new chat session for human-agent or agent-agent interaction",
)
async def create_session(
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=5, seconds=60)),
):
    """Create a new chat session with specified configuration"""
    payload = verify_token(token)
    return await create_session_handler(request, background_tasks, payload["sub"])


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get session status",
    description="Get current status and information about an existing chat session",
)
async def get_session(
    session_id: str,
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=10, seconds=60)),
):
    """Get session information and status"""
    payload = verify_token(token)
    return await get_session_handler(session_id, payload["sub"])


@router.delete(
    "/sessions/{session_id}",
    summary="Delete session",
    description="End and delete a chat session",
)
async def delete_session(
    response: Response,
    session_id: str,
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=5, seconds=60)),
):
    """End a chat session"""
    payload = verify_token(token)
    current_user = payload["sub"]
    return await delete_session_handler(session_id, current_user)


@router.get(
    "/providers",
    summary="Get available providers",
    description="Get list of available AI providers and their models",
)
async def get_providers(
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=10, seconds=60)),
):
    """Get available AI providers and their models"""
    payload = verify_token(token)
    return await get_available_providers(payload["sub"])
