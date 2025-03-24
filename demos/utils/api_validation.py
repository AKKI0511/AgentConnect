from typing import Dict, Optional
import os
from datetime import datetime, UTC, timedelta
from dotenv import load_dotenv
from fastapi import HTTPException, Security, WebSocket, Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from pydantic import BaseModel, Field, field_validator
from jose import jwt, JWTError
from fastapi_limiter.depends import RateLimiter
from uuid import uuid4

from .demo_logger import get_logger
from .config_manager import get_config
from .shared import shared
from agentconnect.core.types import ModelProvider
from demos.api.models.chat import WebSocketMessage, MessageType

logger = get_logger(__name__)
config = get_config()

# Initialize JWT settings
JWT_SECRET_KEY = config.auth_settings["secret_key"]
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.auth_settings["access_token_expire_minutes"]

# Redis key prefixes
WS_CONNECTION_PREFIX = "ws_connection:"
CLIENT_RATE_LIMIT_PREFIX = "rate_limit:"
KEY_ROTATION_PREFIX = "key_rotation:"

# API key header
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/auth/login",
    auto_error=False,
    scopes={"access": "Access protected resources"},
)


class TokenPayload(BaseModel):
    """Model for JWT token payload"""

    sub: str
    exp: datetime
    type: str = "access"
    jti: str = Field(default_factory=lambda: str(uuid4()))  # Unique token ID

    @field_validator("exp")
    def validate_expiration(cls, v):
        if v < datetime.now(UTC):
            raise ValueError("Token has expired")
        return v


class Settings(BaseModel):
    """JWT settings"""

    secret_key: str = config.auth_settings["secret_key"]
    access_token_expire_minutes: int = config.auth_settings[
        "access_token_expire_minutes"
    ]


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token"""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
        "jti": str(uuid4()),
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT verification error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class ProviderKeys(BaseModel):
    """Model for provider API keys"""

    anthropic: Optional[str] = Field(None, min_length=20)
    google: Optional[str] = Field(None, min_length=20)
    openai: Optional[str] = Field(None, min_length=20)
    groq: Optional[str] = Field(None, min_length=20)
    rotation_interval: int = Field(default=30, ge=1)  # Days between key rotations

    @field_validator("*", check_fields=False)
    def validate_keys(cls, v):
        if v and len(str(v).strip()) < 20:
            raise ValueError("API key too short")
        return v


async def track_ws_connection(websocket: WebSocket, session_id: str) -> bool:
    """Track WebSocket connection in Redis"""
    try:
        connection_key = f"{WS_CONNECTION_PREFIX}{session_id}"
        connection_data = {
            "client_id": websocket.client.host,
            "connected_at": datetime.now(UTC).isoformat(),
            "last_heartbeat": datetime.now(UTC).isoformat(),
        }
        await shared.redis.hset(connection_key, mapping=connection_data)
        await shared.redis.expire(connection_key, 3600)  # 1 hour TTL
        return True
    except Exception as e:
        logger.error(f"Error tracking WebSocket connection: {str(e)}")
        return False


async def update_ws_heartbeat(session_id: str) -> bool:
    """Update WebSocket connection heartbeat"""
    try:
        connection_key = f"{WS_CONNECTION_PREFIX}{session_id}"
        await shared.redis.hset(
            connection_key, "last_heartbeat", datetime.now(UTC).isoformat()
        )
        return True
    except Exception as e:
        logger.error(f"Error updating WebSocket heartbeat: {str(e)}")
        return False


async def check_ws_connection_alive(session_id: str, timeout: int = 30) -> bool:
    """Check if WebSocket connection is alive"""
    try:
        connection_key = f"{WS_CONNECTION_PREFIX}{session_id}"
        last_heartbeat = await shared.redis.hget(connection_key, "last_heartbeat")
        if not last_heartbeat:
            return False

        last_beat = datetime.fromisoformat(last_heartbeat)
        return (datetime.now(UTC) - last_beat).total_seconds() <= timeout
    except Exception as e:
        logger.error(f"Error checking WebSocket connection: {str(e)}")
        return False


async def get_api_key(api_key_header: str = Security(API_KEY_HEADER)) -> str:
    """Validate API key"""
    if not api_key_header:
        raise HTTPException(status_code=401, detail="API key missing")

    # Check if API key matches any provider key
    provider_keys = ProviderKeys(
        **{k: v for k, v in config.provider_settings.items() if k != "default_provider"}
    )
    if not any(
        key == api_key_header for key in provider_keys.model_dump().values() if key
    ):
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Check key rotation
    rotation_key = f"{KEY_ROTATION_PREFIX}{api_key_header}"
    last_rotation = await shared.redis.get(rotation_key)
    if not last_rotation:
        await shared.redis.setex(
            rotation_key,
            provider_keys.rotation_interval * 24 * 60 * 60,
            datetime.now(UTC).isoformat(),
        )
    elif (
        datetime.now(UTC) - datetime.fromisoformat(last_rotation)
    ).days >= provider_keys.rotation_interval:
        logger.warning(f"API key should be rotated. Last rotation: {last_rotation}")

    return api_key_header


def get_provider_key(provider: str) -> Optional[str]:
    """Get API key for specific provider"""
    return config.provider_settings.get(provider.lower())


def validate_api_keys(provider: ModelProvider) -> Dict[str, bool]:
    """Validate provider API keys"""
    load_dotenv()

    provider_key_map = {
        ModelProvider.OPENAI: "OPENAI_API_KEY",
        ModelProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        ModelProvider.GROQ: "GROQ_API_KEY",
        ModelProvider.GOOGLE: "GOOGLE_API_KEY",
    }

    key_name = provider_key_map.get(provider)
    api_key = os.getenv(key_name)

    return {
        "is_valid": bool(api_key),
        "key_name": key_name,
        "error_message": f"Missing {key_name} in .env file" if not api_key else None,
    }


async def validate_ws_connection(websocket: WebSocket, session_id: str):
    """Validate WebSocket connection"""
    try:
        session_exists = await shared.redis.exists(f"session:{session_id}")
        return session_exists
    except Exception as e:
        logger.error(f"WebSocket validation error: {str(e)}")
        return False


async def validate_ws_message(message_data: str) -> Optional[WebSocketMessage]:
    """Validate WebSocket message"""
    try:
        message = WebSocketMessage.model_validate_json(message_data)
        if not message.content or not message.content.strip():
            logger.warning("Empty message content")
            return None
        if message.type not in [MessageType.TEXT, MessageType.SYSTEM]:
            logger.warning(f"Invalid message type: {message.type}")
            return None
        return message
    except Exception as e:
        logger.error(f"Message validation error: {str(e)}")
        return None


async def validate_session_access(session_id: str, token: str) -> bool:
    """Validate session access"""
    try:
        verify_token(token)
        return True
    except Exception as e:
        logger.error(f"Session access validation error: {str(e)}")
        return False


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Validate JWT token and return user"""
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_token(token)
        return payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Rate limiting decorators using FastAPI-Limiter
ws_rate_limit = RateLimiter(
    times=int(config.api_settings.get("ws_rate_limit_times", 30)),
    seconds=int(config.api_settings.get("ws_rate_limit_seconds", 60)),
)
api_rate_limit = RateLimiter(
    times=int(config.api_settings.get("api_rate_limit_times", 100)),
    seconds=int(config.api_settings.get("api_rate_limit_seconds", 60)),
)
