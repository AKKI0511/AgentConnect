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
        "agentconnect.config",
        "agentconnect.config.loaders",
        "agentconnect.config.models",
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
        "agentconnect.index.models",
        "agentconnect.index.service",
        "agentconnect.mcp",
        "agentconnect.mcp.server",
        "agentconnect.prebuilt",
        "agentconnect.prebuilt.ai_agent",
        "agentconnect.prebuilt.human_agent",
        "agentconnect.prebuilt.loop",
        "agentconnect.prebuilt.telegram",
        "agentconnect.prebuilt.telegram.telegram_agent",
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


# Public module names do not make all their implementation helpers public.
PUBLIC_MEMBERS = {
    "agentconnect.team.http": {"create_runtime_app"},
    "agentconnect.core.base": {
        "JsonValue",
        "JsonObject",
        "JsonInt",
        "JsonFloat",
        "SchemaModel",
        "parse_schema",
        "dump_public",
        "public_json_schema",
        "public_result_schema",
    },
    "agentconnect.core.identity": {
        "IDENTITY_PROOF_IAT_SKEW_SECONDS",
        "DEFAULT_ATTESTATION_TTL_SECONDS",
        "VerificationStatus",
        "MembershipAttestationClaims",
        "AgentIdentity",
        "did_key_from_public_bytes",
        "public_bytes_from_did_key",
        "is_ed25519_did_key",
        "public_key_pem_from_did",
        "encode_eddsa_jwt",
        "decode_eddsa_jwt",
        "decode_eddsa_jwt_from_did",
        "issue_identity_proof",
        "verify_identity_proof",
        "issue_membership_attestation",
        "verify_membership_attestation",
    },
    "agentconnect.transport.agent_http": {"HttpRuntimeTransport"},
    "agentconnect.transport.inprocess": {"InProcessTransport"},
    "agentconnect.mcp.server": {"create_team_mcp"},
}

# Callers obtain these objects from handle, defer, or team_tools.
NO_PUBLIC_INIT = frozenset(
    {
        "agentconnect.agent.context.Context",
        "agentconnect.agent.context.DeferredReply",
        "agentconnect.agent.tools.TeamTools",
    }
)


def _module_to_relpath(module: str) -> str:
    return (
        "api-reference"
        if module == PACKAGE
        else "api/" + module.removeprefix(PACKAGE + ".").replace(".", "-")
    )


def _is_package_group(module: str, modules: set[str]) -> bool:
    """True for a documented package that has documented child modules."""
    return module != PACKAGE and any(
        name.rpartition(".")[0] == module for name in modules
    )


def _build_nav(modules: set[str]) -> list[Any]:
    """Package groups list Overview first; leaf labels stay short."""

    def children(parent: str) -> list[str]:
        return sorted(name for name in modules if name.rpartition(".")[0] == parent)

    def entry(module: str) -> Any:
        nested = children(module)
        path = _module_to_relpath(module)
        if not nested:
            return path
        return {
            "group": module.rsplit(".", 1)[-1],
            "pages": [path, *[entry(child) for child in nested]],
        }

    top = [entry(module) for module in children(PACKAGE)]
    top.sort(
        key=lambda item: (1, item["group"]) if isinstance(item, dict) else (0, item)
    )
    return [_module_to_relpath(PACKAGE), *top]
