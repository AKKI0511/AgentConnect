from dataclasses import dataclass
from datetime import datetime
import uuid
from typing import Dict, Optional

from src.core.types import MessageType

@dataclass
class Message:
    id: str
    sender_id: str
    receiver_id: str
    content: str
    message_type: MessageType
    timestamp: datetime
    metadata: Optional[Dict] = None

    @classmethod
    def create(cls, sender_id: str, receiver_id: str, content: str, 
               message_type: MessageType = MessageType.TEXT) -> 'Message':
        return cls(
            id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            timestamp=datetime.now(),
            metadata={}
        )