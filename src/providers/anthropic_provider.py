import anthropic
from typing import List, Dict, Any
from .base_provider import BaseProvider
from ..core.types import ModelName
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: ModelName = ModelName.CLAUDE_3_SONNET,
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
            ModelName.CLAUDE_3_OPUS,
            ModelName.CLAUDE_3_SONNET,
            ModelName.CLAUDE_3_HAIKU,
        ]

    def get_langchain_llm(self, model_name: ModelName, **kwargs) -> BaseChatModel:
        return ChatAnthropic(model=model_name.value, api_key=self.api_key, **kwargs)

    def _get_provider_config(self) -> Dict[str, Any]:
        return {"anthropic_api_key": self.api_key, "model_provider": "anthropic"}
