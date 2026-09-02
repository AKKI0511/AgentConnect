"""Agent identity, did:key, join proofs, and membership attestations.

Every Agent has an Ed25519 key pair and a ``did:key`` that is derived from
the public key. The private key stays with the Client. The Runtime stores
the DID and verifies join proofs against it.

    from agentconnect.core.identity import AgentIdentity, issue_identity_proof

    identity = AgentIdentity.create_key_based()
    proof = issue_identity_proof(identity, challenge)

``challenge`` is a :class:`JoinChallenge` from the Runtime. The proof is an
EdDSA JWT. A membership attestation is a separate JWT signed by the Team
key; Cross-team verification of that statement is later work.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional, TypedDict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Multicodec prefix for ed25519-pub (varint of 0xed).
_ED25519_MULTICODEC = b"\xed\x01"
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_DID_KEY = re.compile(r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{22,64}$")
_AUDIENCE = re.compile(r"^agentconnect:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_IDENTITY_PROOF_CLAIMS = frozenset({"iss", "aud", "nonce", "iat", "exp"})
_ATTESTATION_TYP = "ac-membership+jwt"
IDENTITY_PROOF_IAT_SKEW_SECONDS = 60
DEFAULT_ATTESTATION_TTL_SECONDS = 365 * 24 * 60 * 60


class VerificationStatus(str, Enum):
    """Whether this identity has been locally checked."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class MembershipAttestationClaims(TypedDict):
    """Decoded membership attestation. The Team signed this statement.

    A third party can later verify the JWT with the Team's public key. The
    current Runtime mints the token at join and does not verify inbound
    attestations.
    """

    issuer_did: str
    agent_did: str
    team_name: str
    name: str
    address: str
    issued_at: int
    expires_at: int


def utc_now() -> datetime:
    """Return the current UTC time with tzinfo set."""
    return datetime.now(timezone.utc)


def b58encode(data: bytes) -> str:
    """Encode ``data`` as Bitcoin base58 (no checksum)."""
    n = int.from_bytes(data, "big")
    out: list[str] = []
    while n > 0:
        n, rem = divmod(n, 58)
        out.append(_B58[rem])
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    body = "".join(reversed(out)) if out else ""
    return (_B58[0] * pad) + body


def b58decode(value: str) -> bytes:
    """Decode Bitcoin base58 (no checksum). Raises ValueError on bad input."""
    if not value:
        raise ValueError("base58 value is empty")
    n = 0
    for char in value:
        idx = _B58.find(char)
        if idx < 0:
            raise ValueError("base58 value contains an invalid character")
        n = n * 58 + idx
    pad = 0
    for char in value:
        if char == _B58[0]:
            pad += 1
        else:
            break
    if n == 0:
        return b"\x00" * pad
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return (b"\x00" * pad) + body


def did_key_from_public_bytes(raw: bytes) -> str:
    """Return a ``did:key`` for a 32-byte Ed25519 public key."""
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return "did:key:z" + b58encode(_ED25519_MULTICODEC + raw)


def public_bytes_from_did_key(did: str) -> bytes:
    """Return the 32-byte Ed25519 public key encoded in ``did``.

    Raises ValueError when ``did`` is not an Ed25519 ``did:key``.
    """
    if not isinstance(did, str) or _DID_KEY.fullmatch(did) is None:
        raise ValueError("agent_did must be a did:key identifier")
    payload = b58decode(did[len("did:key:z") :])
    if not payload.startswith(_ED25519_MULTICODEC) or len(payload) != 34:
        raise ValueError("did:key does not encode an Ed25519 public key")
    return payload[2:]


def is_ed25519_did_key(did: str) -> bool:
    """Return True when ``did`` is an Ed25519 ``did:key``."""
    try:
        public_bytes_from_did_key(did)
        return True
    except ValueError:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise ValueError("JWT is not valid base64url") from exc


def _load_private_key(pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    return key


def _load_public_key(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("public key is not Ed25519")
    return key


def public_key_pem_from_did(did: str) -> str:
    """Return a SubjectPublicKeyInfo PEM for an Ed25519 ``did:key``."""
    raw = public_bytes_from_did_key(did)
    key = Ed25519PublicKey.from_public_bytes(raw)
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def encode_eddsa_jwt(
    payload: Mapping[str, Any],
    private_key_pem: str,
    *,
    typ: str = "JWT",
) -> str:
    """Return a compact EdDSA JWT signed with ``private_key_pem``."""
    header = {"alg": "EdDSA", "typ": typ}
    signing_input = (
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url_encode(
            json.dumps(dict(payload), separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )
    )
    signature = _load_private_key(private_key_pem).sign(signing_input.encode("ascii"))
    return signing_input + "." + _b64url_encode(signature)


def split_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    """Split a compact JWT. Does not verify the signature.

    Returns ``(header, payload, signing_input, signature)``.
    """
    if not isinstance(token, str) or token.count(".") != 2:
        raise ValueError("JWT must have three compact segments")
    encoded_header, encoded_payload, encoded_sig = token.split(".")
    try:
        header = json.loads(_b64url_decode(encoded_header))
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("JWT header or payload is not JSON") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise ValueError("JWT header and payload must be objects")
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = _b64url_decode(encoded_sig)
    return header, payload, signing_input, signature


def decode_eddsa_jwt(token: str, public_key_pem: str) -> dict[str, Any]:
    """Verify an EdDSA JWT and return its payload.

    Raises ValueError when the token is malformed or the signature is wrong.
    """
    header, payload, signing_input, signature = split_jwt(token)
    if header.get("alg") != "EdDSA":
        raise ValueError("JWT alg must be EdDSA")
    try:
        _load_public_key(public_key_pem).verify(signature, signing_input)
    except InvalidSignature as exc:
        raise ValueError("JWT signature is invalid") from exc
    return payload


def decode_eddsa_jwt_from_did(token: str, did: str) -> dict[str, Any]:
    """Verify an EdDSA JWT with the Ed25519 key encoded in ``did``."""
    return decode_eddsa_jwt(token, public_key_pem_from_did(did))


@dataclass
class AgentIdentity:
    """Ed25519 ``did:key`` identity for one Agent.

    ``create_key_based`` mints a new key pair. Pass the result to
    ``BaseAgent(name=..., identity=identity)`` when you want a stable DID
    across process restarts.

        identity = AgentIdentity.create_key_based()
        agent = Researcher(name="researcher", identity=identity)
    """

    did: str
    public_key: str
    private_key: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def create_key_based(cls) -> "AgentIdentity":
        """Create an identity with a generated Ed25519 key pair and ``did:key``."""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        did = did_key_from_public_bytes(raw)
        return cls(
            did=did,
            public_key=public_pem,
            private_key=private_pem,
            verification_status=VerificationStatus.VERIFIED,
            metadata={
                "key_type": "Ed25519",
                "creation_method": "key_based",
            },
        )

    def public_bytes(self) -> bytes:
        """Return the 32-byte Ed25519 public key."""
        return _load_public_key(self.public_key).public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def matches_did(self) -> bool:
        """Return True when ``did`` is the ``did:key`` for ``public_key``."""
        try:
            return public_bytes_from_did_key(self.did) == self.public_bytes()
        except ValueError:
            return False

    def sign_message(self, message: str) -> str:
        """Sign ``message`` and return a standard-base64 Ed25519 signature."""
        if not self.private_key:
            raise ValueError("Private key not available for signing")
        signature = _load_private_key(self.private_key).sign(message.encode("utf-8"))
        return base64.b64encode(signature).decode("ascii")

    def verify_signature(self, message: str, signature: str) -> bool:
        """Return True when ``signature`` matches ``message`` under the public key."""
        try:
            _load_public_key(self.public_key).verify(
                base64.b64decode(signature),
                message.encode("utf-8"),
            )
            return True
        except Exception:
            return False

    def to_dict(self) -> Dict:
        """Return a serializable public view. The private key is omitted."""
        created = self.created_at
        if created.tzinfo is None:
            created_s = created.isoformat()
        else:
            created_s = created.astimezone(timezone.utc).isoformat()
        return {
            "did": self.did,
            "public_key": self.public_key,
            "verification_status": self.verification_status.value,
            "created_at": created_s,
            "metadata": self.metadata,
        }

    def to_secret_dict(self) -> Dict:
        """Return :meth:`to_dict` plus the private key when present.

        For Runtime storage of the Team key. Never send this to a Client.
        """
        data = self.to_dict()
        if self.private_key:
            data["private_key"] = self.private_key
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentIdentity":
        """Create an identity from ``to_dict`` or :meth:`to_secret_dict` output."""
        created_raw = data["created_at"]
        created = datetime.fromisoformat(created_raw)
        return cls(
            did=data["did"],
            public_key=data["public_key"],
            private_key=data.get("private_key"),
            verification_status=VerificationStatus(data["verification_status"]),
            created_at=created,
            metadata=data.get("metadata", {}),
        )


def parse_rfc3339(value: str) -> datetime:
    """Parse an RFC 3339 UTC timestamp ending in ``Z``."""
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC 3339 UTC ending in Z")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def issue_identity_proof(
    identity: AgentIdentity,
    challenge: Mapping[str, Any],
    *,
    now: Optional[datetime] = None,
) -> str:
    """Return an EdDSA JWT proving control of ``identity.did``.

    Required claims are ``iss``, ``aud``, ``nonce``, ``iat``, and ``exp``.
    ``iss`` is the Agent DID. ``aud`` and ``nonce`` copy the challenge.
    ``exp`` is the challenge expiry.

        proof = issue_identity_proof(agent.identity, challenge)
    """
    if not identity.private_key:
        raise ValueError("Private key not available for signing")
    nonce = challenge.get("nonce")
    audience = challenge.get("audience")
    expires_at = challenge.get("expires_at")
    if not isinstance(nonce, str) or _NONCE.fullmatch(nonce) is None:
        raise ValueError("challenge nonce is invalid")
    if not isinstance(audience, str) or _AUDIENCE.fullmatch(audience) is None:
        raise ValueError("challenge audience is invalid")
    if not isinstance(expires_at, str):
        raise ValueError("challenge expires_at is invalid")
    expires = parse_rfc3339(expires_at)
    instant = now or utc_now()
    iat = int(instant.timestamp())
    exp = int(expires.timestamp())
    if exp <= iat:
        raise ValueError("challenge has already expired")
    payload = {
        "iss": identity.did,
        "aud": audience,
        "nonce": nonce,
        "iat": iat,
        "exp": exp,
    }
    return encode_eddsa_jwt(payload, identity.private_key)


def verify_identity_proof(
    token: str,
    *,
    agent_did: str,
    challenge: Mapping[str, Any],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Verify a join ``identity_proof`` JWT.

    Checks the Ed25519 signature against ``agent_did``, then the required
    claims against ``challenge``. Raises ValueError on any failure. Callers
    that must not reveal which check failed should map that to ``unauthorized``.
    """
    header, payload, signing_input, signature = split_jwt(token)
    if header.get("alg") != "EdDSA" or header.get("typ") != "JWT":
        raise ValueError("identity_proof header is invalid")
    if set(payload.keys()) != _IDENTITY_PROOF_CLAIMS:
        raise ValueError("identity_proof claims are invalid")
    if payload.get("iss") != agent_did:
        raise ValueError("identity_proof iss does not match agent_did")
    pem = public_key_pem_from_did(agent_did)
    try:
        _load_public_key(pem).verify(signature, signing_input)
    except InvalidSignature as exc:
        raise ValueError("identity_proof signature is invalid") from exc
    nonce = challenge.get("nonce")
    audience = challenge.get("audience")
    expires_at = challenge.get("expires_at")
    if payload.get("aud") != audience:
        raise ValueError("identity_proof aud does not match the challenge")
    if payload.get("nonce") != nonce:
        raise ValueError("identity_proof nonce does not match the challenge")
    iat = payload.get("iat")
    exp = payload.get("exp")
    if not isinstance(iat, int) or not isinstance(exp, int):
        raise ValueError("identity_proof iat and exp must be integers")
    instant = now or utc_now()
    now_ts = int(instant.timestamp())
    if iat > now_ts + IDENTITY_PROOF_IAT_SKEW_SECONDS:
        raise ValueError("identity_proof iat is too far in the future")
    if exp <= iat:
        raise ValueError("identity_proof exp must be later than iat")
    if not isinstance(expires_at, str):
        raise ValueError("challenge expires_at is invalid")
    challenge_exp = int(parse_rfc3339(expires_at).timestamp())
    if exp > challenge_exp:
        raise ValueError("identity_proof exp is after the challenge expiry")
    if exp <= now_ts:
        raise ValueError("identity_proof has expired")
    return payload


def issue_membership_attestation(
    team_identity: AgentIdentity,
    *,
    agent_did: str,
    name: str,
    address: str,
    team_name: str,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_ATTESTATION_TTL_SECONDS,
) -> str:
    """Return a Team-signed JWT that this Team vouches for ``agent_did``.

    Header ``typ`` is ``ac-membership+jwt``. Claims:

    - ``iss``: Team DID
    - ``sub``: Agent DID
    - ``aud``: ``agentconnect:<team-name>``
    - ``name``: Agent name in this Team
    - ``address``: qualified Address
    - ``iat`` / ``exp``

    Nothing in the current Runtime verifies this token. Store it and present
    it later at a Team boundary.

        jwt = issue_membership_attestation(
            team.identity,
            agent_did=agent.agent_did,
            name="writer",
            address="writer@content-squad",
            team_name="content-squad",
        )
    """
    if not team_identity.private_key:
        raise ValueError("Team private key not available for signing")
    if not is_ed25519_did_key(agent_did):
        raise ValueError("agent_did must be an Ed25519 did:key")
    instant = now or utc_now()
    iat = int(instant.timestamp())
    exp = int((instant + timedelta(seconds=int(ttl_seconds))).timestamp())
    payload = {
        "iss": team_identity.did,
        "sub": agent_did,
        "aud": f"agentconnect:{team_name}",
        "name": name,
        "address": address,
        "iat": iat,
        "exp": exp,
    }
    return encode_eddsa_jwt(payload, team_identity.private_key, typ=_ATTESTATION_TYP)


def verify_membership_attestation(
    token: str,
    *,
    team_did: str,
    now: Optional[datetime] = None,
) -> MembershipAttestationClaims:
    """Verify a membership attestation JWT against ``team_did``.

    Provided so the format is testable. The Runtime does not call this on
    inbound work.
    """
    header, payload, signing_input, signature = split_jwt(token)
    if header.get("alg") != "EdDSA" or header.get("typ") != _ATTESTATION_TYP:
        raise ValueError("membership attestation header is invalid")
    if payload.get("iss") != team_did:
        raise ValueError("membership attestation iss does not match team_did")
    pem = public_key_pem_from_did(team_did)
    try:
        _load_public_key(pem).verify(signature, signing_input)
    except InvalidSignature as exc:
        raise ValueError("membership attestation signature is invalid") from exc
    required = ("iss", "sub", "aud", "name", "address", "iat", "exp")
    for key in required:
        if key not in payload:
            raise ValueError("membership attestation is missing a required claim")
    iat = payload["iat"]
    exp = payload["exp"]
    if not isinstance(iat, int) or not isinstance(exp, int):
        raise ValueError("membership attestation iat and exp must be integers")
    instant = now or utc_now()
    if exp <= int(instant.timestamp()):
        raise ValueError("membership attestation has expired")
    agent_did = payload["sub"]
    if not isinstance(agent_did, str) or not is_ed25519_did_key(agent_did):
        raise ValueError("membership attestation sub is not an Ed25519 did:key")
    aud = payload["aud"]
    name = payload["name"]
    address = payload["address"]
    if not isinstance(aud, str) or not aud.startswith("agentconnect:"):
        raise ValueError("membership attestation aud is invalid")
    if not isinstance(name, str) or not isinstance(address, str):
        raise ValueError("membership attestation name or address is invalid")
    return {
        "issuer_did": team_did,
        "agent_did": agent_did,
        "team_name": aud.split(":", 1)[1],
        "name": name,
        "address": address,
        "issued_at": iat,
        "expires_at": exp,
    }
