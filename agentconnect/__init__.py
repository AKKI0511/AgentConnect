"""
AgentConnect - A decentralized framework for autonomous agent collaboration.

This package provides tools for creating, managing, and connecting independent AI agents
capable of dynamic discovery and secure, autonomous communication across distributed networks.

Key components:
- Agents: Independent agent implementations (AI, Human) with their own internal structures
- Core: Foundational types, message handling, and registry for capability-based discovery
- Communication: Decentralized hub for agent-to-agent secure messaging
- Providers: LLM provider integrations for autonomous agent intelligence
- Prompts: Tools, workflows, and templates for agent interactions
- Utils: Utility functions for security, interaction control, verification, etc.

Key differentiators:
- Decentralized Architecture: Agents operate as independent, autonomous peers rather than in a hierarchy
- Dynamic Discovery: Agents find each other based on capabilities, not pre-defined connections
- Independent Operation: Each agent can have its own internal multi-agent system
- Secure Communication: Built-in cryptographic message signing and verification
- Horizontal Scalability: Designed for thousands of independent, collaborating agents

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
