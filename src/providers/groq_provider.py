from typing import List, Dict, Any
from .base_provider import BaseProvider
from ..core.types import ModelName


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
            ModelName.MIXTRAL,
            ModelName.LLAMA3_70B,
            ModelName.LLAMA3_8B,
            ModelName.LLAMA33_70B_VTL,
            ModelName.GEMMA2_90B,
            ModelName.LLAMA_GUARD3_8B,
        ]

    def _get_provider_config(self) -> Dict[str, Any]:
        return {"groq_api_key": self.api_key, "model_provider": "groq"}
