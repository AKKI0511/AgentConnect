from groq import AsyncGroq
from typing import List, Dict
from .base_provider import BaseProvider
from ..core.types import ModelName


class GroqProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncGroq(api_key=api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.MIXTRAL,
        **kwargs,
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                messages=messages, model=model.value, **kwargs
            )
            return response.choices[0].message.content
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
