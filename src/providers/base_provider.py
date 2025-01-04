from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from src.core.types import ModelName


class BaseProvider(ABC):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @abstractmethod
    async def generate_response(
        self, messages: List[Dict[str, str]], model: ModelName, **kwargs
    ) -> str:
        pass

    @abstractmethod
    def get_available_models(self) -> List[ModelName]:
        pass
