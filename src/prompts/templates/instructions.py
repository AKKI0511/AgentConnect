from dataclasses import dataclass
from enum import Enum
from typing import List


class InstructionType(Enum):
    GENERAL = "general"
    CODING = "coding"
    ANALYSIS = "analysis"


@dataclass
class InstructionSet:
    type: InstructionType
    instructions: List[str]
    guidelines: List[str]


class Instructions:
    @staticmethod
    def get_instruction_set(
        type: InstructionType = InstructionType.GENERAL,
    ) -> InstructionSet:
        instruction_sets = {
            InstructionType.GENERAL: InstructionSet(
                type=InstructionType.GENERAL,
                instructions=[
                    "Maintain conversation context",
                    "Be concise but informative",
                    "Ask for clarification when needed",
                ],
                guidelines=[
                    "Use clear language",
                    "Stay on topic",
                    "Acknowledge uncertainties",
                ],
            ),
            InstructionType.CODING: InstructionSet(
                type=InstructionType.CODING,
                instructions=[
                    "Analyze code thoroughly",
                    "Suggest best practices",
                    "Explain changes clearly",
                ],
                guidelines=[
                    "Include code examples",
                    "Consider performance",
                    "Follow language conventions",
                ],
            ),
        }
        return instruction_sets.get(type, instruction_sets[InstructionType.GENERAL])
