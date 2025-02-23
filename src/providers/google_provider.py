import os
from typing import List, Dict, Any
from .base_provider import BaseProvider
from ..core.types import ModelName


class GoogleProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.GEMINI1_5_FLASH,
        **kwargs,
    ) -> str:
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            return f"Google AI Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [ModelName.GEMINI1_5_FLASH, ModelName.GEMINI1_5_PRO]

    def _get_provider_config(self) -> Dict[str, Any]:
        return {"gemini_api_key": self.api_key, "model_provider": "google_genai"}


if __name__ == "__main__":
    provider = GoogleProvider(os.getenv("GOOGLE_API_KEY"))
    print(provider.get_available_models())
