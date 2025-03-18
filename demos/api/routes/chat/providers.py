from fastapi import HTTPException, status
from demos.utils.demo_logger import get_logger
from agentconnect.providers.provider_factory import ProviderFactory

logger = get_logger("chat_providers")


async def get_available_providers(current_user: str) -> dict:
    """Get available providers and their models"""
    logger.info(f"Getting available providers for user {current_user}")
    try:
        providers = ProviderFactory.get_available_providers()
        logger.debug(f"Found {len(providers)} available providers")
        for provider, data in providers.items():
            logger.debug(f"Provider {provider} has {len(data['models'])} models")
        return providers
    except Exception as e:
        logger.error(f"Error getting available providers: {str(e)}")
        raise


async def get_available_providers_old(current_user: str):
    """Get available providers and models"""
    try:
        return ProviderFactory.get_available_providers()
    except Exception as e:
        logger.error(f"Error getting providers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
