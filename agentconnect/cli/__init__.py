"""
AgentConnect CLI package.

Provides a minimal, production-ready command line interface composed of
focused subcommands with clear boundaries between SDK config and server config.
"""

from .main import app  # re-export for console script entrypoint

__all__ = ["app"]
