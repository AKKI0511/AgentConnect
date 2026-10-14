"""Supported reference modules and Mintlify navigation policy."""

from typing import Any

PACKAGE = "agentconnect"

PUBLIC_MODULES = frozenset(
    {
        "agentconnect",
        "agentconnect.agent",
        "agentconnect.agent.base",
        "agentconnect.agent.context",
        "agentconnect.agent.errors",
        "agentconnect.agent.identity",
        "agentconnect.agent.tools",
        "agentconnect.cli",
        "agentconnect.compat",
        "agentconnect.config",
        "agentconnect.config.loaders",
        "agentconnect.config.models",
        "agentconnect.config.servers",
        "agentconnect.config.vector",
        "agentconnect.core",
        "agentconnect.core.address",
        "agentconnect.core.base",
        "agentconnect.core.directory",
        "agentconnect.core.error",
        "agentconnect.core.identity",
        "agentconnect.core.kinds",
        "agentconnect.core.message",
        "agentconnect.core.operations",
        "agentconnect.core.primitives",
        "agentconnect.core.profile",
        "agentconnect.core.spec",
        "agentconnect.core.ticket",
        "agentconnect.index",
        "agentconnect.index.client",
        "agentconnect.index.service",
        "agentconnect.index.types",
        "agentconnect.mcp",
        "agentconnect.mcp.server",
        "agentconnect.prebuilt",
        "agentconnect.prebuilt.ai_agent",
        "agentconnect.prebuilt.human_agent",
        "agentconnect.prebuilt.loop",
        "agentconnect.prebuilt.telegram",
        "agentconnect.prebuilt.telegram.telegram_agent",
        "agentconnect.prebuilt.tools",
        "agentconnect.team",
        "agentconnect.team.directory",
        "agentconnect.team.directory.embedder",
        "agentconnect.team.errors",
        "agentconnect.team.http",
        "agentconnect.team.runtime",
        "agentconnect.team.store",
        "agentconnect.team.store.base",
        "agentconnect.team.store.memory",
        "agentconnect.team.store.ops",
        "agentconnect.team.store.redis",
        "agentconnect.transport",
        "agentconnect.transport.agent_http",
        "agentconnect.transport.inprocess",
        "agentconnect.transport.runtime",
    }
)


def _module_to_relpath(module: str) -> str:
    return (
        "api-reference"
        if module == PACKAGE
        else "api/" + module.removeprefix(PACKAGE + ".").replace(".", "-")
    )


def _build_nav(modules: set[str]) -> list[Any]:
    """Keep package pages as group roots and leaf labels short."""

    def children(parent: str) -> list[str]:
        return sorted(name for name in modules if name.rpartition(".")[0] == parent)

    def entry(module: str) -> Any:
        nested = children(module)
        path = _module_to_relpath(module)
        if not nested:
            return path
        return {
            "group": module.rsplit(".", 1)[-1],
            "root": path,
            "pages": [entry(child) for child in nested],
        }

    top = [entry(module) for module in children(PACKAGE)]
    top.sort(
        key=lambda item: (1, item["group"]) if isinstance(item, dict) else (0, item)
    )
    return [_module_to_relpath(PACKAGE), *top]
