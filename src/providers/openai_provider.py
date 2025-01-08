from typing import List, Dict, Any
from .base_provider import BaseProvider
from ..core.types import ModelName


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.GPT35_TURBO,
        **kwargs,
    ) -> str:
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            return f"OpenAI Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [ModelName.GPT4_TURBO, ModelName.GPT4, ModelName.GPT35_TURBO]

    def _get_provider_config(self) -> Dict[str, Any]:
        return {"openai_api_key": self.api_key, "model_provider": "openai"}
