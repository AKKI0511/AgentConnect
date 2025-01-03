from enum import Enum


class AgentType(Enum):
    HUMAN = "human"
    AI = "ai"


class MessageType(Enum):
    TEXT = "text"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"
