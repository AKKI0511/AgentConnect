import openai
from typing import List, Dict
from .base_provider import BaseProvider
from ..core.types import ModelName


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        openai.api_key = api_key

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.GPT35_TURBO,
        **kwargs,
    ) -> str:
        try:
            response = await openai.ChatCompletion.acreate(
                model=model.value, messages=messages, **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [ModelName.GPT4_TURBO, ModelName.GPT4, ModelName.GPT35_TURBO]
