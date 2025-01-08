# NOTE: This file is not currently useable
# Future integration: PostgreSQL, Redis

from typing import List, Optional, Dict, Any
from enum import Enum
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel
import redis
import json


class MemoryType(Enum):
    BUFFER = "buffer"
    SUMMARY = "summary"
    REDIS = "redis"


class MessageState(BaseModel):
    messages: List[Dict[str, str]]


class MemoryManager:
    def __init__(
        self,
        memory_type: MemoryType = MemoryType.BUFFER,
        session_id: str = None,
        redis_url: Optional[str] = None,
        **kwargs: Dict[str, Any]
    ):
        self.memory_type = memory_type
        self.session_id = session_id
        self.redis_url = redis_url
        self.kwargs = kwargs
        self.state = MessageState(messages=[])
        self._initialize_memory()

    def _initialize_memory(self):
        if self.memory_type == MemoryType.REDIS and self.redis_url:
            self.redis_client = redis.from_url(self.redis_url)
            # Load existing messages from Redis if any
            if self.session_id:
                stored_messages = self.redis_client.get(self.session_id)
                if stored_messages:
                    self.state.messages = json.loads(stored_messages)

        elif self.memory_type == MemoryType.SUMMARY:
            # Initialize with empty state, summary will be computed on demand
            pass

    async def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        message = {"role": role.lower(), "content": content}
        self.state.messages.append(message)

        # If using Redis, persist the updated messages
        if self.memory_type == MemoryType.REDIS and self.redis_url and self.session_id:
            self.redis_client.set(self.session_id, json.dumps(self.state.messages))

    def get_memory(self):
        """Returns a memory object compatible with LangChain's ConversationChain."""
        return {
            "messages": self.state.messages,
            "load_memory_variables": self._load_memory_variables,
            "save_context": self._save_context,
            "clear": self.clear,
        }

    def _load_memory_variables(
        self, inputs: Dict[str, Any]
    ) -> Dict[str, List[BaseMessage]]:
        """Load memory variables in a format compatible with LangChain."""
        messages = []
        for msg in self.state.messages:
            if msg["role"] == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] in ["ai", "assistant"]:
                messages.append(AIMessage(content=msg["content"]))
        return {"chat_history": messages}

    def _save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save the context of the conversation."""
        if "input" in inputs:
            self.state.messages.append({"role": "human", "content": inputs["input"]})
        if "output" in outputs:
            self.state.messages.append(
                {"role": "assistant", "content": outputs["output"]}
            )

        # Persist to Redis if configured
        if self.memory_type == MemoryType.REDIS and self.redis_url and self.session_id:
            self.redis_client.set(self.session_id, json.dumps(self.state.messages))

    def get_memory_state(self) -> Dict[str, List[BaseMessage]]:
        """Returns the current chat history as a dictionary."""
        return self._load_memory_variables({})

    def clear(self) -> None:
        """Clears all messages from memory."""
        self.state.messages = []
        if self.memory_type == MemoryType.REDIS and self.redis_url and self.session_id:
            self.redis_client.delete(self.session_id)

    def get_messages(self) -> List[BaseMessage]:
        """Returns all messages in the chat history."""
        return [msg for msg in self._load_memory_variables({})["chat_history"]]

    def format_messages(self, messages: List[Dict[str, str]]) -> List[BaseMessage]:
        """Format raw messages into BaseMessage objects."""
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "human":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] in ["ai", "assistant"]:
                formatted_messages.append(AIMessage(content=msg["content"]))
        return formatted_messages
