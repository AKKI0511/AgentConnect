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

from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:  # running from source without install
    __version__ = "0"

# Only the version is exported by default
__all__ = ["__version__"]

import logging

# Attach a NullHandler to the package logger to avoid "No handler" warnings
# and ensure the library never emits logs unless the application configures logging.
logging.getLogger("agentconnect").addHandler(logging.NullHandler())
