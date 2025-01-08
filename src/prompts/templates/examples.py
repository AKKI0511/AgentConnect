from typing import List, Dict
from enum import Enum


class ConversationType(Enum):
    GENERAL = "general"
    CODING = "coding"
    ANALYSIS = "analysis"


class ExampleTemplates:
    _examples = {
        ConversationType.GENERAL: [
            {
                "user": "What did we discuss earlier about X?",
                "assistant": "Let me check our conversation history specifically about X...",
            },
            {
                "user": "Can you remember my first question?",
                "assistant": "Yes, looking at our conversation history, your first question was...",
            },
        ],
        ConversationType.CODING: [
            {
                "user": "Can you help me debug this code?",
                "assistant": "I'll analyze the code and help identify any issues...",
            },
            {
                "user": "How can I improve this function?",
                "assistant": "Let me review the function and suggest improvements...",
            },
        ],
        ConversationType.ANALYSIS: [
            {
                "user": "Can you analyze this data?",
                "assistant": "I'll examine the data and provide insights...",
            }
        ],
    }

    @classmethod
    def get_conversation_examples(
        cls, conv_type: ConversationType = ConversationType.GENERAL
    ) -> List[Dict[str, str]]:
        return cls._examples.get(conv_type, cls._examples[ConversationType.GENERAL])
