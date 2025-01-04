import anthropic
from typing import List, Dict
from .base_provider import BaseProvider
from ..core.types import ModelName


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
            # Convert messages to Anthropic format
            system_message = next(
                (m["content"] for m in messages if m["role"] == "system"), None
            )
            message_content = " ".join(
                m["content"] for m in messages if m["role"] != "system"
            )

            response = await self.client.messages.create(
                model=model.value,
                max_tokens=kwargs.get("max_tokens", 1024),
                system=system_message,
                messages=[{"role": "user", "content": message_content}],
            )
            return response.content[0].text
        except Exception as e:
            return f"Anthropic Error: {str(e)}"

    def get_available_models(self) -> List[ModelName]:
        return [
            ModelName.CLAUDE_3_OPUS,
            ModelName.CLAUDE_3_SONNET,
            ModelName.CLAUDE_3_HAIKU,
        ]
