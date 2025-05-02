"""
AgentConnect - A decentralized framework for autonomous agent collaboration.

This package provides tools for creating, managing, and connecting independent AI agents
capable of dynamic discovery and secure, autonomous communication across distributed networks.

Key components:

- **Agents**: Independent agent implementations (AI, Human) with their own internal structures
- **Core**: Foundational types, message handling, and registry for capability-based discovery
- **Communication**: Decentralized hub for agent-to-agent secure messaging
- **Providers**: LLM provider integrations for autonomous agent intelligence
- **Prompts**: Tools, workflows, and templates for agent interactions
- **Utils**: Utility functions for security, interaction control, verification, etc.

Key differentiators:

- **Decentralized Architecture**: Agents operate as independent, autonomous peers rather than in a hierarchy
- **Dynamic Discovery**: Agents find each other based on capabilities, not pre-defined connections
- **Independent Operation**: Each agent can have its own internal multi-agent system
- **Secure Communication**: Built-in cryptographic message signing and verification
- **Horizontal Scalability**: Designed for thousands of independent, collaborating agents

For detailed usage examples, see the README.md or visit the documentation.
"""

__version__ = "0.3.0"

# Import subpackages to make them available to users
from agentconnect import agents
from agentconnect import communication
from agentconnect import core
from agentconnect import providers
from agentconnect import prompts
from agentconnect import utils

# Define public API - specify what should be exposed when a user does "from agentconnect import *"
__all__ = [
    "agents",
    "communication",
    "core",
    "providers",
    "prompts",
    "utils",
    "__version__",
]
