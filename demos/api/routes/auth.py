from fastapi import APIRouter, HTTPException, Depends, status, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_limiter.depends import RateLimiter
from datetime import datetime, timedelta

from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.api_validation import create_access_token
from demos.api.models.chat import Token

router = APIRouter()
logger = get_logger("auth_routes")
config = get_config()

# OAuth2PasswordBearer is a class that implements the OAuth2 specification
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    rate_limiter: bool = Depends(RateLimiter(times=10, seconds=60)),
):
    """Login to get access token"""
    try:
        # Validate user credentials
        if not config.validate_user(form_data.username, form_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        # Get user details
        user = config.get_user(form_data.username)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive"
            )

        # Create access token
        access_token_expires = timedelta(
            minutes=config.auth_settings["access_token_expire_minutes"]
        )
        access_token = create_access_token(
            subject=form_data.username, expires_delta=access_token_expires
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=config.auth_settings["access_token_expire_minutes"] * 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/verify")
async def verify_token(
    response: Response,
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=50, seconds=60)),
):
    """Verify token validity"""
    try:
        from demos.utils.api_validation import verify_token as verify_jwt_token

        payload = verify_jwt_token(token)

        return {
            "valid": True,
            "user": payload["sub"],
            "type": payload.get("type", "access"),
            "exp": payload.get("exp", None),
            "iat": payload.get("iat", None),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
