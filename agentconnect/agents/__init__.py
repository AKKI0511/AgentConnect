"""
Independent agent implementations for the AgentConnect decentralized framework.

This module provides various autonomous agent implementations that operate as independent entities
in a decentralized network. Each agent maintains its own identity, capabilities, and can optionally
implement its own internal multi-agent system while communicating with other agents through
capability-based discovery.

Key components:

- **AIAgent**: Independent AI-powered agent with potential for internal multi-agent structures
- **HumanAgent**: Human-in-the-loop agent that can interact securely with the decentralized network
- **TelegramAIAgent**: AI agent that integrates with Telegram for user interactions
- **MemoryType**: Enum for different types of agent memory

Each agent operates autonomously and can discover and communicate with other agents based on
capabilities rather than pre-defined connections, enabling a truly decentralized architecture.
"""

from agentconnect.agents.ai_agent import AIAgent, MemoryType
from agentconnect.agents.human_agent import HumanAgent
from agentconnect.agents.telegram import TelegramAIAgent

__all__ = ["AIAgent", "HumanAgent", "TelegramAIAgent", "MemoryType"]
