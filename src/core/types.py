from enum import Enum
from typing import Dict, Any, Optional

class AgentType(Enum):
    HUMAN = "human"
    AI = "ai"

class MessageType(Enum):
    TEXT = "text"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"