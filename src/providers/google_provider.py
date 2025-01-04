import google.generativeai as genai
from typing import List, Dict
from .base_provider import BaseProvider
from ..core.types import ModelName


class GoogleProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        genai.configure(api_key=api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.GEMINI_PRO,
        **kwargs,
    ) -> str:
        try:
            model = genai.GenerativeModel(model.value)
            chat = model.start_chat()

            for message in messages:
                if message["role"] == "user":
                    response = chat.send_message(message["content"])

            return response.text
        except Exception as e:
            return f"Google AI Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [ModelName.GEMINI_PRO, ModelName.GEMINI_PRO_VISION]
