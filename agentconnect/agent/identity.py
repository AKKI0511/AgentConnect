"""Filesystem persistence for Agent identities.

``BaseAgent(identity_path=...)`` loads or creates the key file. Callers
that already hold an ``AgentIdentity`` can use the same JSON helpers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agentconnect.core.identity import AgentIdentity


def save_identity(identity: AgentIdentity, path: str | Path) -> None:
    """Write ``identity``, including the private key, to ``path``.

    The file is JSON. Anyone who can read it can impersonate the Agent.
    On POSIX the file mode is set to ``0o600`` when the OS allows it.

        save_identity(identity, "researcher.json")
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(identity.to_secret_dict(), indent=2, sort_keys=True)
    target.write_text(payload + "\n", encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def load_identity(path: str | Path) -> AgentIdentity:
    """Read an identity previously written by :func:`save_identity`.

    identity = load_identity("researcher.json")
    """
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"identity file is not readable JSON: {target}") from exc
    if not isinstance(raw, dict):
        raise ValueError("identity file must contain a JSON object")
    try:
        identity = AgentIdentity.from_dict(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"identity file is invalid: {target}") from exc
    if not identity.private_key:
        raise ValueError("identity file is missing the private key")
    if not identity.matches_did():
        raise ValueError("identity file DID does not match the public key")
    return identity


def load_or_create_identity(path: str | Path) -> AgentIdentity:
    """Load ``path`` when it exists, otherwise mint a key and save it.

    Restarting an Agent with the same path keeps the same DID.

        identity = load_or_create_identity("researcher.json")
    """
    target = Path(path)
    if target.is_file():
        return load_identity(target)
    identity = AgentIdentity.create_key_based()
    save_identity(identity, target)
    return identity
