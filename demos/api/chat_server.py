"""
FastAPI server implementation for the chat application
"""

import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from jose import JWTError
import uvicorn


# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from demos.api.routes import auth
from demos.api.routes import agents, chat
from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.shared import shared
from demos.utils.task_manager import add_background_task, cleanup_background_tasks
from demos.api.middleware import (
    LoggingMiddleware,
    ErrorHandlingMiddleware,
    WebSocketMiddleware,
)

# Setup logging
logger = get_logger("api")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application"""
    try:
        # Initialize Redis
        await shared.init_redis()

        # Clean up old data
        await shared.cleanup_redis_data()

        # Initialize rate limiter
        await FastAPILimiter.init(shared.redis)
        logger.info("API startup completed successfully")

        yield

    except Exception as e:
        logger.error(f"Failed to initialize API services: {str(e)}")
        raise
    finally:
        logger.info("Starting API shutdown process...")

        try:
            # First cleanup background tasks
            await cleanup_background_tasks()

            # Then cleanup shared resources
            await shared.cleanup()
            await FastAPILimiter.close()
            logger.info("API shutdown completed successfully")

        except Exception as e:
            logger.error(f"Error during API shutdown: {str(e)}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="AgentConnect Demo API",
        description="""
        API for demonstrating agent-to-agent and human-to-agent communication.
        
        Features:
        * Real-time chat using WebSocket
        * Multiple AI provider support
        * Session management
        * JWT authentication
        """,
        version="1.0.0",
        debug=config.api_settings["debug"],
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api_settings["allowed_origins"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(WebSocketMiddleware)

    # Error handler for JWT errors
    @app.exception_handler(JWTError)
    async def jwt_error_handler(request: Request, exc: JWTError):
        return JSONResponse(
            status_code=401, content={"detail": "Invalid authentication credentials"}
        )

    # Add routers
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(agents.router, prefix="/api/agents", tags=["agents"])

    @app.get("/", tags=["health"])
    async def health_check():
        """Health check endpoint"""
        try:
            # Check Redis connection
            if shared.redis:
                await shared.redis.ping()

            return {
                "status": "healthy",
                "service": "AgentConnect Demo API",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "detail": "Service dependencies unavailable",
                    "timestamp": datetime.now().isoformat(),
                },
            )

    # Custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="AgentConnect Demo API",
            version="1.0.0",
            description="API for agent-to-agent and human-to-agent communication",
            routes=app.routes,
        )

        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Custom documentation endpoints
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="AgentConnect Demo API - Documentation",
            swagger_favicon_url="/static/favicon.ico",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="AgentConnect Demo API - ReDoc",
            redoc_favicon_url="/static/favicon.ico",
        )

    @app.middleware("http")
    async def add_background_task_tracking(request: Request, call_next):
        """Track background tasks for cleanup"""
        response = await call_next(request)

        # Get background tasks from request state if any
        if hasattr(request.state, "background_tasks"):
            for task in request.state.background_tasks:
                if not task.done():
                    add_background_task(task)

        return response

    return app


def run_app(host: str = "127.0.0.1", port: int = 8000):
    """Run the application"""
    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=config.logging_settings["level"].lower(),
        timeout_keep_alive=30,
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    run_app(host=config.api_settings["host"], port=config.api_settings["port"])
