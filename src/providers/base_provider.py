from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from src.core.types import ModelName


class BaseProvider(ABC):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Any]:
        """Convert dict messages to LangChain message objects"""
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                formatted_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                formatted_messages.append(AIMessage(content=msg["content"]))
        return formatted_messages

    async def generate_response(
        self, messages: List[Dict[str, str]], model: ModelName, **kwargs
    ) -> str:
        try:
            llm = self.get_langchain_llm(model, **kwargs)
            formatted_messages = self._format_messages(messages)
            response = await llm.ainvoke(formatted_messages)
            return response.content
        except Exception as e:
            return f"Provider Error: {str(e)}"

    @abstractmethod
    def get_available_models(self) -> List[ModelName]:
        pass

    def get_langchain_llm(self, model_name: ModelName, **kwargs) -> BaseChatModel:
        """Returns a LangChain chat model instance using init_chat_model"""
        config = {"model": model_name.value, **self._get_provider_config(), **kwargs}
        return init_chat_model(**config)

    @abstractmethod
    def _get_provider_config(self) -> Dict[str, Any]:
        """Returns provider-specific configuration"""
        pass


if __name__ == "__main__":
    provider = BaseProvider()
    print(provider.get_available_models())
