from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain.prompts import SystemMessagePromptTemplate


@dataclass
class SystemPromptConfig:
    name: str
    capabilities: List[str]
    personality: str = "helpful and professional"
    temperature: float = 0.7
    max_tokens: int = 150
    additional_context: Optional[Dict[str, Any]] = None


class SystemPrompts:
    @staticmethod
    def get_assistant_prompt(config: SystemPromptConfig) -> SystemMessagePromptTemplate:
        template = """You are {name}, an AI agent with capabilities: {capabilities}

Personality: {personality}

Core Instructions:
1. Perfect conversation history memory
2. Precise and accurate responses
3. Reference previous conversations
4. Acknowledge uncertainty
5. Focus on user needs with context
6. Be brutally honest (DON'T LIE)

Responses should be:
- Clear, SHORT and concise
- Contextually aware
- Logically connected

NOTE: If you have nothing to contribute, simply say '__EXIT__' and nothing else."""

        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "name": config.name,
                "capabilities": ", ".join(config.capabilities),
                "personality": config.personality,
            },
        )
