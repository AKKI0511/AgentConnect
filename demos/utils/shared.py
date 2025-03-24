"""
Shared instances module to prevent duplicate initialization
"""

from typing import Optional, Set
import redis.asyncio as redis
from agentconnect.core.registry import AgentRegistry
from agentconnect.communication.hub import CommunicationHub
from demos.utils.demo_logger import get_logger
import asyncio
import weakref
import logging

# Initialize logger using our centralized system with explicit INFO level
logger = get_logger(__name__)
logger.setLevel(logging.INFO)  # Ensure INFO level


class SharedResources:
    """Singleton class to manage shared resources"""

    _instance = None
    _redis: Optional[redis.Redis] = None
    _registry: Optional[AgentRegistry] = None
    _hub: Optional[CommunicationHub] = None
    _websocket_connections: Set = set()
    _cleanup_lock: Optional[asyncio.Lock] = None
    _is_shutting_down: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._cleanup_lock = asyncio.Lock()
            cls._websocket_connections = weakref.WeakSet()
        return cls._instance

    @property
    def redis(self) -> Optional[redis.Redis]:
        return self._redis

    @property
    def registry(self) -> AgentRegistry:
        if not self._registry:
            self._registry = AgentRegistry()
        return self._registry

    @property
    def hub(self) -> CommunicationHub:
        if not self._hub:
            self._hub = CommunicationHub(self.registry)
        return self._hub

    def register_websocket(self, websocket) -> None:
        """Register a WebSocket connection for cleanup"""
        self._websocket_connections.add(websocket)

    def unregister_websocket(self, websocket) -> None:
        """Unregister a WebSocket connection"""
        self._websocket_connections.discard(websocket)

    async def init_redis(self) -> None:
        """Initialize Redis connection with error handling"""
        max_retries = 3
        retry_delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                if not self._redis:
                    self._redis = redis.from_url(
                        "redis://localhost",
                        encoding="utf-8",
                        decode_responses=True,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        health_check_interval=30,
                        max_connections=10,
                        retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                    )
                    # Test connection
                    await self._redis.ping()
                    logger.info("Redis connection established successfully")
                    return

            except redis.ConnectionError as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to connect to Redis after {max_retries} attempts: {str(e)}"
                    )
                    raise RuntimeError("Redis connection failed") from e
                logger.warning(
                    f"Redis connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds"
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

            except Exception as e:
                logger.error(f"Unexpected error initializing Redis: {str(e)}")
                raise RuntimeError("Redis initialization failed") from e

    async def cleanup_redis_data(self) -> None:
        """Clean up Redis data with proper locking"""
        if not self._redis:
            return

        async with self._cleanup_lock:
            try:
                patterns = ["user_sessions:*", "session:*", "rate-limit:*"]
                for pattern in patterns:
                    async for key in self._redis.scan_iter(pattern):
                        try:
                            await self._redis.delete(key)
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete Redis key {key}: {str(e)}"
                            )
                logger.info("Redis data cleanup completed")
            except Exception as e:
                logger.error(f"Error during Redis data cleanup: {str(e)}")

    async def close_redis(self) -> None:
        """Close Redis connection with proper error handling"""
        if not self._redis:
            return

        async with self._cleanup_lock:
            try:
                await self._redis.aclose()
                await asyncio.sleep(0.1)  # Brief pause to ensure cleanup
                logger.info("Redis connection closed successfully")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")
            finally:
                self._redis = None

    async def cleanup(self) -> None:
        """Comprehensive cleanup of all resources"""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True

        try:
            # Close all WebSocket connections
            websocket_tasks = []
            for ws in list(self._websocket_connections):
                try:
                    websocket_tasks.append(ws.close())
                except Exception as e:
                    logger.warning(f"Error closing WebSocket connection: {str(e)}")

            if websocket_tasks:
                await asyncio.gather(*websocket_tasks, return_exceptions=True)

            # Cleanup Redis data and close connection
            await self.cleanup_redis_data()
            await self.close_redis()

            # Clear registry and hub
            if self._registry:
                self._registry = None
            if self._hub:
                self._hub = None

            logger.info("All resources cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during resource cleanup: {str(e)}")
        finally:
            self._is_shutting_down = False


# Create single instance to be shared across the application
shared = SharedResources()
