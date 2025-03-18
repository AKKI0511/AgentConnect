import os
from typing import Any, Dict, List

from ..core.types import ModelName
from .base_provider import BaseProvider


class GroqProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.MIXTRAL,
        **kwargs,
    ) -> str:
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            return f"Groq Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [
            ModelName.LLAMA33_70B_VTL,
            ModelName.LLAMA3_1_8B_INSTANT,
            ModelName.LLAMA3_70B,
            ModelName.LLAMA3_8B,
            ModelName.LLAMA_GUARD3_8B,
            ModelName.MIXTRAL,
            ModelName.GEMMA2_90B,
        ]

    def _get_provider_config(self) -> Dict[str, Any]:
        return {"groq_api_key": self.api_key, "model_provider": "groq"}


if __name__ == "__main__":
    provider = GroqProvider(os.getenv("GROQ_API_KEY"))
    print(provider.get_available_models())
