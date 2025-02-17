from fastapi import Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from fastapi.responses import JSONResponse
from jose import JWTError
import asyncio

from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.shared import shared

logger = get_logger("middleware")
config = get_config()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Simple logging middleware for HTTP requests"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Basic paths to exclude from logging
        self.excluded_paths = {"/docs", "/redoc", "/openapi.json", "/"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Skip WebSocket requests
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Only log non-successful responses and important endpoints
            if response.status_code >= 400:
                logger.warning(
                    f"{request.method} {request.url.path} "
                    f"- Status: {response.status_code} "
                    f"- Duration: {process_time:.3f}s"
                )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url.path} "
                f"- Error: {str(e)} "
                f"- Duration: {process_time:.3f}s"
            )
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Simple error handling middleware"""

    async def dispatch(self, request: Request, call_next):
        try:
            if request.headers.get("upgrade", "").lower() == "websocket":
                return await call_next(request)

            response = await call_next(request)
            return response

        except JWTError as e:
            # Handle JWT authentication errors
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication credentials: " + str(e)},
            )
        except Exception as e:
            # Handle all other errors
            logger.error(f"Error in {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )


class WebSocketMiddleware:
    """WebSocket connection management middleware with proper cleanup"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            websocket = None
            try:
                websocket = WebSocket(scope=scope, receive=receive, send=send)

                # Register WebSocket connection for cleanup
                shared.register_websocket(websocket)

                # Pass through to endpoint handler first
                await self.app(scope, receive, send)

            except Exception as e:
                logger.error(f"WebSocket middleware error: {str(e)}")
                if websocket:
                    try:
                        shared.unregister_websocket(websocket)
                        await websocket.close(code=1011)
                    except Exception as e:
                        logger.error(f"Error closing WebSocket: {str(e)}")
                        pass
        else:
            await self.app(scope, receive, send)

    async def _keep_alive(self, websocket: WebSocket):
        """Keep WebSocket connection alive with ping/pong"""
        try:
            while True:
                try:
                    await websocket.send_json({"type": "ping"})
                    await asyncio.sleep(30)  # Send ping every 30 seconds
                except Exception as e:
                    logger.warning(f"Error in WebSocket keep-alive: {str(e)}")
                    break
        except asyncio.CancelledError:
            pass
