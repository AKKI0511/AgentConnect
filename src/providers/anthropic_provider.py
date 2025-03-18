import os
from typing import Any, Dict, List

import anthropic
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

from ..core.types import ModelName
from .base_provider import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.CLAUDE_3_5_HAIKU,
        **kwargs,
    ) -> str:
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            return f"Anthropic Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [
            ModelName.CLAUDE_3_5_SONNET,
            ModelName.CLAUDE_3_5_HAIKU,
            ModelName.CLAUDE_3_OPUS,
            ModelName.CLAUDE_3_SONNET,
            ModelName.CLAUDE_3_HAIKU,
        ]

    def get_langchain_llm(self, model_name: ModelName, **kwargs) -> BaseChatModel:
        return ChatAnthropic(model=model_name.value, api_key=self.api_key, **kwargs)

    def _get_provider_config(self) -> Dict[str, Any]:
        return {"anthropic_api_key": self.api_key, "model_provider": "anthropic"}


if __name__ == "__main__":
    provider = AnthropicProvider(os.getenv("ANTHROPIC_API_KEY"))
    print(provider.get_available_models())
