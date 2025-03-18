from typing import Dict, Any, Optional, List
from functools import lru_cache
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
import os
import json
from uuid import uuid4
from dotenv import load_dotenv
from demos.utils.demo_logger import get_logger
from agentconnect.core.types import ModelName, ModelProvider

# Initialize logger using our centralized system
logger = get_logger("config_manager")


class UserCredentials(BaseModel):
    """User credentials model"""

    username: str
    password_hash: str
    role: str = "user"
    is_active: bool = True


class AuthSettings(BaseModel):
    """Authentication settings"""

    secret_key: str = Field(default_factory=lambda: str(uuid4()))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    users_file: Path = Field(
        default_factory=lambda: Path(__file__).parent / "users.json"
    )

    @field_validator("users_file")
    def validate_users_file(cls, v: Path):
        if not v.exists():
            # Create default users file with demo credentials
            default_users = {
                "demo": {
                    "username": "demo",
                    "password_hash": "demo123",  # In production, this should be properly hashed
                    "role": "user",
                    "is_active": True,
                }
            }
            v.parent.mkdir(parents=True, exist_ok=True)
            v.write_text(json.dumps(default_users, indent=2))
            logger.info("Created default users file with demo credentials")
        return v

    def get_user(self, username: str) -> Optional[UserCredentials]:
        """Get user credentials"""
        try:
            if not self.users_file.exists():
                self.validate_users_file(self.users_file)
            users = json.loads(self.users_file.read_text())
            if username in users:
                return UserCredentials(**users[username])
            return None
        except Exception as e:
            logger.error(f"Error reading users file: {str(e)}")
            return None

    def validate_user(self, username: str, password: str) -> bool:
        """Validate user credentials"""
        user = self.get_user(username)
        if not user or not user.is_active:
            return False
        # TODO: In production, use proper password hashing
        return user.password_hash == password


class APISettings(BaseModel):
    """API settings"""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    allowed_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:4173",
    ]  # Vite's default port
    ws_rate_limit_times: int = 30
    ws_rate_limit_seconds: int = 60
    api_rate_limit_times: int = 100
    api_rate_limit_seconds: int = 60


class LoggingSettings(BaseModel):
    """Logging settings"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logs_dir: Path = Field(
        default_factory=lambda: Path(__file__).parents[2] / "demos" / "logs"
    )

    @field_validator("level")
    def validate_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            return "INFO"
        return v


class SessionSettings(BaseModel):
    """Session settings"""

    timeout: int = 3600  # 1 hour
    websocket_timeout: int = 300  # 5 minutes
    max_sessions_per_user: int = 5
    max_messages_per_session: int = 50
    max_session_duration: int = 3600  # 1 hour
    max_inactive_time: int = 300  # 5 minutes without messages


class ProviderSettings(BaseModel):
    """Provider settings"""

    anthropic: Optional[str] = None
    openai: Optional[str] = None
    groq: Optional[str] = None
    google: Optional[str] = None
    default_provider: ModelProvider = ModelProvider.GROQ
    default_model: ModelName = ModelName.LLAMA3_70B


class Config(BaseModel):
    """Main configuration class"""

    auth_settings: AuthSettings = Field(default_factory=AuthSettings)
    api_settings: APISettings = Field(default_factory=APISettings)
    logging_settings: LoggingSettings = Field(default_factory=LoggingSettings)
    session_settings: SessionSettings = Field(default_factory=SessionSettings)
    provider_settings: ProviderSettings = Field(default_factory=ProviderSettings)


class ConfigManager:
    """Centralized configuration manager for the application"""

    def __init__(self):
        self._config = self._load_config()
        self._runtime_overrides: Dict[str, Any] = {}

    def _load_config(self) -> Config:
        """Load configuration with validation"""
        try:
            load_dotenv()

            # API settings with defaults
            api_settings = {
                "host": os.getenv("API_HOST", "127.0.0.1"),
                "port": int(os.getenv("API_PORT", "8000")),
                "debug": os.getenv("DEBUG", "False").lower() == "true",
                "allowed_origins": os.getenv(
                    "ALLOWED_ORIGINS", "http://localhost:5173"
                ).split(","),
                "ws_rate_limit_times": int(os.getenv("WS_RATE_LIMIT_TIMES", "30")),
                "ws_rate_limit_seconds": int(os.getenv("WS_RATE_LIMIT_SECONDS", "60")),
                "api_rate_limit_times": int(os.getenv("API_RATE_LIMIT_TIMES", "100")),
                "api_rate_limit_seconds": int(
                    os.getenv("API_RATE_LIMIT_SECONDS", "60")
                ),
            }

            # Session settings with defaults
            session_settings = {
                "timeout": int(os.getenv("SESSION_TIMEOUT", "3600")),
                "websocket_timeout": int(os.getenv("WEBSOCKET_TIMEOUT", "300")),
                "max_messages_per_session": int(
                    os.getenv("MAX_MESSAGES_PER_SESSION", "1000")
                ),
                "max_inactive_time": int(os.getenv("MAX_INACTIVE_TIME", "1800")),
                "max_session_duration": int(os.getenv("MAX_SESSION_DURATION", "86400")),
                "max_sessions_per_user": int(os.getenv("MAX_SESSIONS_PER_USER", "5")),
            }

            # Default agent settings with defaults
            default_agent_settings = {
                "provider": ModelProvider(os.getenv("DEFAULT_PROVIDER", "groq")),
                "model": ModelName(
                    os.getenv("DEFAULT_MODEL", "llama-3.3-70b-versatile")
                ),
                "max_tokens_per_minute": int(
                    os.getenv("MAX_TOKENS_PER_MINUTE", "5500")
                ),
                "max_tokens_per_hour": int(os.getenv("MAX_TOKENS_PER_HOUR", "100000")),
            }

            # Provider API keys (these are optional except for the default provider)
            provider_api_keys = {
                "anthropic": os.getenv("ANTHROPIC_API_KEY"),
                "openai": os.getenv("OPENAI_API_KEY"),
                "groq": os.getenv("GROQ_API_KEY"),
                "google": os.getenv("GOOGLE_API_KEY"),
            }

            # Ensure at least one provider key is available
            default_provider = default_agent_settings["provider"]
            if not provider_api_keys.get(default_provider):
                logger.warning(
                    f"API key for default provider '{default_provider}' is missing"
                )

            # Authentication settings with defaults
            auth_settings = {
                "secret_key": os.getenv("AUTH_SECRET_KEY", str(uuid4())),
                "algorithm": "HS256",
                "access_token_expire_minutes": int(
                    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
                ),
                "refresh_token_expire_days": int(
                    os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
                ),
            }

            # Create Config instance with all settings
            return Config(
                auth_settings=AuthSettings(**auth_settings),
                api_settings=APISettings(**api_settings),
                logging_settings=LoggingSettings(
                    level=os.getenv("LOG_LEVEL", "INFO"),
                    format=os.getenv(
                        "LOG_FORMAT",
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    ),
                    logs_dir=Path(__file__).parents[2] / "demos" / "logs",
                ),
                session_settings=SessionSettings(**session_settings),
                provider_settings=ProviderSettings(
                    anthropic=provider_api_keys["anthropic"],
                    openai=provider_api_keys["openai"],
                    groq=provider_api_keys["groq"],
                    google=provider_api_keys["google"],
                    default_provider=default_agent_settings["provider"],
                    default_model=default_agent_settings["model"],
                ),
            )

        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            # Instead of raising an error, return a default configuration
            return Config(
                auth_settings=AuthSettings(),
                api_settings=APISettings(),
                logging_settings=LoggingSettings(),
                session_settings=SessionSettings(),
                provider_settings=ProviderSettings(),
            )

    @property
    def auth_settings(self) -> Dict:
        return self._config.auth_settings.model_dump()

    @property
    def api_settings(self) -> Dict:
        return self._config.api_settings.model_dump()

    @property
    def logging_settings(self) -> Dict:
        return self._config.logging_settings.model_dump()

    @property
    def session_settings(self) -> Dict:
        return self._config.session_settings.model_dump()

    @property
    def provider_settings(self) -> Dict:
        return self._config.provider_settings.model_dump()

    @property
    def default_agent_settings(self) -> Dict[str, ModelProvider | ModelName]:
        """Get default agent settings"""
        return {
            "provider": self._config.provider_settings.default_provider,
            "model": self._config.provider_settings.default_model,
        }

    def get_provider_api_key(self, provider: str) -> Optional[str]:
        """Get API key for specific provider"""
        return getattr(self._config.provider_settings, provider.lower(), None)

    def override_setting(self, key: str, value: Any) -> None:
        """Override a configuration setting at runtime"""
        self._runtime_overrides[key] = value

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting with runtime override support"""
        if key in self._runtime_overrides:
            return self._runtime_overrides[key]

        # Try to find the setting in nested configs
        parts = key.split(".")
        config = self._config
        try:
            for part in parts:
                config = getattr(config, part)
            return config
        except AttributeError:
            return default

    def validate_user(self, username: str, password: str) -> bool:
        """Validate user credentials"""
        return self._config.auth_settings.validate_user(username, password)

    def get_user(self, username: str) -> Optional[UserCredentials]:
        """Get user credentials"""
        return self._config.auth_settings.get_user(username)


@lru_cache()
def get_config() -> ConfigManager:
    """Get or create singleton ConfigManager instance"""
    return ConfigManager()
