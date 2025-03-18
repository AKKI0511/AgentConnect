"""
Agent implementations for the AgentConnect framework.

This module provides various agent implementations, including AI agents and human agents,
that can communicate with each other and perform tasks based on their capabilities.

Key components:
- AIAgent: AI-powered agent implementation
- HumanAgent: Human-in-the-loop agent implementation
- MemoryType: Enum for different types of agent memory
"""

from agentconnect.agents.ai_agent import AIAgent, MemoryType
from agentconnect.agents.human_agent import HumanAgent

__all__ = ["AIAgent", "HumanAgent", "MemoryType"]
