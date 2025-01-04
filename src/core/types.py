from enum import Enum


class ModelProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    GOOGLE = "google"
    META = "meta"
    XMISTRAL = "mistral"
    OLLAMA = "ollama"


class ModelName(Enum):
    # OpenAI Models
    GPT4_TURBO = "gpt-4-turbo-preview"
    GPT4 = "gpt-4"
    GPT35_TURBO = "gpt-3.5-turbo"

    # Anthropic Models
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"

    # Groq Models
    MIXTRAL = "mixtral-8x7b-32768"
    LLAMA3_70B = "llama3-70b-8192"
    LLAMA3_8B = "llama3-8b-8192"
    LLAMA33_70B_VTL = "llama-3.3-70b-versatile"
    LLAMA_GUARD3_8B = "llama-guard-3-8b"
    GEMMA2_90B = "gemma2-9b-it"

    # Google Models
    GEMINI_PRO = "gemini-pro"
    GEMINI_PRO_VISION = "gemini-pro-vision"

    # Meta Models (via Ollama)
    LLAMA2_7B = "llama2:7b"
    LLAMA2_13B = "llama2:13b"
    LLAMA2_70B_OLLAMA = "llama2:70b"

    # Mistral Models
    MISTRAL_TINY = "mistral-tiny"
    MISTRAL_SMALL = "mistral-small"
    MISTRAL_MEDIUM = "mistral-medium"


class AgentType(Enum):
    HUMAN = "human"
    AI = "ai"


class MessageType(Enum):
    TEXT = "text"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"
