"""
AgentConnect - A framework for connecting and managing AI agents.

This package provides tools for creating, managing, and connecting AI agents
for autonomous communication and collaboration.

Key components:
- Agents: Base agent classes and implementations (AI, Human)
- Core: Foundational types, message handling, and registry
- Communication: Hub for agent-to-agent messaging
- Providers: LLM provider integrations
- Prompts: Tools, workflows, and templates for agent interactions
- Utils: Utility functions for security, interaction control, etc.

For detailed usage examples, see the README.md or visit the documentation.
"""

__version__ = "0.1.0"

# We only re-export the bare minimum needed for the public API
# Everything else should be imported from submodules directly
from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.human_agent import HumanAgent
from agentconnect.communication.hub import CommunicationHub
from agentconnect.providers.provider_factory import ProviderFactory

# We don't directly expose these in the public API, but they can be imported with:
# from agentconnect.core import Message, AgentType, Capability, etc.

# Define public API - only include what is directly imported above
__all__ = [
    # Agents
    "AIAgent",
    "HumanAgent",
    # Communication
    "CommunicationHub",
    # Providers
    "ProviderFactory",
    # Version
    "__version__",
]
