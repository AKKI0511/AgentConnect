"""
AgentConnect - A decentralized framework for autonomous agent collaboration.

This package provides tools for creating, managing, and connecting independent AI agents
capable of dynamic discovery and secure, autonomous communication across distributed networks.

Key components:

- **core**: nouns with no I/O (Message, Address, identity, Profile, kinds)
- **agent**: client SDK (`BaseAgent`)
- **team**: runtime, tickets, and directory
- **transport**: in-process and HTTP delivery
- **mcp**: team tool surface
- **gateway**: inbound work from outside the process
- **index**: optional published-directory service and client
- **prebuilt**: ready-made agents behind extras
- **providers** / **prompts**: helper internals until the helper rebuild

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

# Only the version is exported by default; names below load on attribute access.
__all__ = [
    "__version__",
    "BaseAgent",
    "Context",
    "SessionError",
    "Team",
    "TeamError",
]

import logging

# Attach a NullHandler to the package logger to avoid "No handler" warnings
# and ensure the library never emits logs unless the application configures logging.
logging.getLogger("agentconnect").addHandler(logging.NullHandler())

_LAZY_EXPORTS = {
    "BaseAgent": ("agentconnect.agent.base", "BaseAgent"),
    "Context": ("agentconnect.agent.context", "Context"),
    "SessionError": ("agentconnect.agent.errors", "SessionError"),
    "Team": ("agentconnect.team.runtime", "Team"),
    "TeamError": ("agentconnect.team.errors", "TeamError"),
}


def __getattr__(name: str):
    """Load Team and Agent types without importing the whole package tree."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    return getattr(import_module(module_name), attr)
