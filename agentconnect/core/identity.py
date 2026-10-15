"""Agent-owned keys, join proofs and Team-signed membership statements.

Persist the Agent's key when you need to reconnect to its retained Membership.
A join proof shows key control for a fresh Runtime challenge. A membership
attestation is a separate statement signed by the Team; it does not grant
admission or Session authority. The Runtime does not accept inbound attestations.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional, TypedDict

from agentconnect.core.base import JsonObject, JsonValue
from agentconnect.core.operations import JoinChallenge
from agentconnect.core.primitives import AgentDid

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
_IDENTITY_PROOF_CLAIMS = frozenset({"iss", "aud", "nonce", "iat", "exp"})
_ATTESTATION_TYP = "ac-membership+jwt"
IDENTITY_PROOF_IAT_SKEW_SECONDS = 60
"""Seconds of clock skew allowed for identity-proof `iat` in the future."""
DEFAULT_ATTESTATION_TTL_SECONDS = 365 * 24 * 60 * 60
"""Default membership-attestation lifetime in seconds (365 days)."""


class VerificationStatus(str, Enum):
    """Whether this identity has been locally checked.

    Attributes:
        PENDING: Not yet checked.
        VERIFIED: Public key matches the DID.
        FAILED: Local check failed.
    """

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class MembershipAttestationClaims(TypedDict):
    """Membership claims from a verified Team-signed statement.

    These describe what the signer asserted, rather than current Session authority.

    Attributes:
        issuer_did: Team identity used to verify the signature.
        agent_did: Agent identity the signer vouches for.
        team_name: Team named by the statement's audience.
        name: Membership name recorded by the signer.
        address: Qualified membership Address recorded by the signer.
        issued_at: Unix issuance time in seconds.
        expires_at: Unix expiry time in seconds.
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
    """Encode `data` as Bitcoin base58 (no checksum).

    Args:
        data: Raw bytes, including a `did:key` multicodec prefix.
    """
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
    """Decode Bitcoin base58 (no checksum).

    Args:
        value: Base58 text without a check suffix.

    Raises:
        ValueError: `value` is empty or contains an invalid character.
    """
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
    """Derive an Agent DID from a raw Ed25519 public key.

    Raises:
        ValueError: The key is not 32 bytes.
    """
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return "did:key:z" + b58encode(_ED25519_MULTICODEC + raw)


def public_bytes_from_did_key(did: str) -> bytes:
    """Read the raw Ed25519 public key encoded in an Agent DID.

    Raises:
        ValueError: The DID does not encode an Ed25519 key.
    """
    if not isinstance(did, str) or _DID_KEY.fullmatch(did) is None:
        raise ValueError("agent_did must be a did:key identifier")
    payload = b58decode(did[len("did:key:z") :])
    if not payload.startswith(_ED25519_MULTICODEC) or len(payload) != 34:
        raise ValueError("did:key does not encode an Ed25519 public key")
    return payload[2:]


def is_ed25519_did_key(did: str) -> bool:
    """Return whether the DID encodes a 32-byte Ed25519 public key."""
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
    """Convert an Agent DID to its SubjectPublicKeyInfo public-key PEM.

    Raises:
        ValueError: The DID does not encode an Ed25519 key.
    """
    raw = public_bytes_from_did_key(did)
    key = Ed25519PublicKey.from_public_bytes(raw)
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def encode_eddsa_jwt(
    payload: Mapping[str, JsonValue],
    private_key_pem: str,
    *,
    typ: str = "JWT",
) -> str:
    """Sign claims as a compact EdDSA JWT.

    Args:
        private_key_pem: Ed25519 key in PKCS8 PEM form.
        typ: Token category to include in the JWT header.

    Raises:
        ValueError: The PEM is not an Ed25519 private key.
    """
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


def split_jwt(token: str) -> tuple[JsonObject, JsonObject, bytes, bytes]:
    """Split a compact JWT. Does not verify the signature.

    Args:
        token: Compact `header.payload.signature` string.

    Raises:
        ValueError: The token is not three segments, or a segment is not JSON.
    """
    if not isinstance(token, str) or token.count(".") != 2:
        raise ValueError("JWT must have three compact segments")
    encoded_header, encoded_payload, encoded_sig = token.split(".")
    try:
        header: JsonValue = json.loads(_b64url_decode(encoded_header))
        payload: JsonValue = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("JWT header or payload is not JSON") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise ValueError("JWT header and payload must be objects")
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = _b64url_decode(encoded_sig)
    return header, payload, signing_input, signature


def decode_eddsa_jwt(token: str, public_key_pem: str) -> JsonObject:
    """Verify an EdDSA signature and return the JWT payload.

    This checks the signature, rather than expiry, audience or other claim policy.

    Args:
        public_key_pem: Expected signer's SubjectPublicKeyInfo PEM.

    Raises:
        ValueError: The token or signature is invalid.
    """
    header, payload, signing_input, signature = split_jwt(token)
    if header.get("alg") != "EdDSA":
        raise ValueError("JWT alg must be EdDSA")
    try:
        _load_public_key(public_key_pem).verify(signature, signing_input)
    except InvalidSignature as exc:
        raise ValueError("JWT signature is invalid") from exc
    return payload


def decode_eddsa_jwt_from_did(token: str, did: str) -> JsonObject:
    """Verify a JWT signature using the key in the expected signer's DID.

    Does not validate expiry, audience or other claim policy.

    Raises:
        ValueError: The DID, token or signature is invalid.
    """
    return decode_eddsa_jwt(token, public_key_pem_from_did(did))


@dataclass
class AgentIdentity:
    """An Agent's Ed25519 key identity.

    `create_key_based` creates a new identity. Pass a retained identity to
    `BaseAgent`, or use `identity_path` there to load or create a key file.
    Creating another key cannot reclaim an existing Membership's name.

    Attributes:
        did: Identifier derived from the public key.
        public_key: SubjectPublicKeyInfo PEM.
        private_key: PKCS8 PEM; absent on a public-only view.
        verification_status: Local key/DID check, rather than Team admission.
        created_at: Object creation time; not Team admission time.
        metadata: Application information included in serialized views.
    """

    did: str
    public_key: str
    private_key: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def create_key_based(cls) -> "AgentIdentity":
        """Create a new key pair with its derived DID and verified local status."""
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
        """Return the raw 32-byte public key.

        Raises:
            ValueError: The stored public key is not an Ed25519 PEM.
        """
        return _load_public_key(self.public_key).public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def matches_did(self) -> bool:
        """Return whether the public key matches the DID; malformed keys or DIDs return False."""
        try:
            return public_bytes_from_did_key(self.did) == self.public_bytes()
        except ValueError:
            return False

    def sign_message(self, message: str) -> str:
        """Sign UTF-8 text and return a standard-base64 Ed25519 signature.

        Raises:
            ValueError: This identity has no private key.
        """
        if not self.private_key:
            raise ValueError("Private key not available for signing")
        signature = _load_private_key(self.private_key).sign(message.encode("utf-8"))
        return base64.b64encode(signature).decode("ascii")

    def verify_signature(self, message: str, signature: str) -> bool:
        """Verify a standard-base64 Ed25519 signature over UTF-8 text.

        Malformed keys or signatures return False.
        """
        try:
            _load_public_key(self.public_key).verify(
                base64.b64decode(signature),
                message.encode("utf-8"),
            )
            return True
        except Exception:
            return False

    def to_dict(self) -> JsonObject:
        """Return a serializable public view with the private key left out."""
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

    def to_secret_dict(self) -> JsonObject:
        """Return a serializable identity including its private key when available.

        Use for trusted key persistence. This result can sign as the identity;
        keep it out of Messages and public responses.
        """
        data = self.to_dict()
        if self.private_key:
            data["private_key"] = self.private_key
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentIdentity":
        """Restore a serialized identity; a public view cannot restore a missing private key."""
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
    """Parse an RFC 3339 UTC timestamp ending in `Z`.

    Args:
        value: Timestamp such as `2026-08-18T15:00:00Z`.

    Raises:
        ValueError: `value` is not RFC 3339 UTC ending in `Z`.
    """
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC 3339 UTC ending in Z")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def issue_identity_proof(
    identity: AgentIdentity,
    challenge: JoinChallenge,
    *,
    now: Optional[datetime] = None,
) -> str:
    """Sign a fresh Runtime challenge to prove control of the Agent DID.

    Send the JWT as `identity_proof` alongside the Team's join invitation. The
    proof alone does not authorize admission.

    Args:
        identity: Must hold the Agent private key.
        challenge: Runtime JoinChallenge, including audience, nonce and expiry.
        now: Override the current UTC clock used for issuance.

    Raises:
        ValueError: The private key is absent or the challenge is invalid or expired.
    """
    if not identity.private_key:
        raise ValueError("Private key not available for signing")
    nonce = challenge.nonce
    audience = challenge.audience
    expires_at = challenge.expires_at
    expires = parse_rfc3339(expires_at)
    instant = now or utc_now()
    iat = int(instant.timestamp())
    exp = int(expires.timestamp())
    if exp <= iat:
        raise ValueError("challenge has already expired")
    payload: JsonObject = {
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
    agent_did: AgentDid,
    challenge: JoinChallenge,
    now: Optional[datetime] = None,
) -> JsonObject:
    """Verify key control and claims against the supplied join challenge.

    The caller must ensure the challenge is issued, unused and consumed atomically
    with admission. This cryptographic check does not consume it.

    Args:
        agent_did: Expected proof issuer.
        now: Override the current UTC clock for expiry and issuance skew.

    Raises:
        ValueError: The token, signature, timing or challenge claims are invalid.
            Admission callers should expose a single `unauthorized` failure.
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
    nonce = challenge.nonce
    audience = challenge.audience
    expires_at = challenge.expires_at
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
    challenge_exp = int(parse_rfc3339(expires_at).timestamp())
    if exp > challenge_exp:
        raise ValueError("identity_proof exp is after the challenge expiry")
    if exp <= now_ts:
        raise ValueError("identity_proof has expired")
    return payload


def issue_membership_attestation(
    team_identity: AgentIdentity,
    *,
    agent_did: AgentDid,
    name: str,
    address: str,
    team_name: str,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_ATTESTATION_TTL_SECONDS,
) -> str:
    """Sign a statement that this Team vouches for an Agent's membership.

    The statement includes the Agent DID, Team, name, Address and lifetime.
    It is separate from join invitations and Session credentials. The current
    Runtime issues these statements but does not admit callers using them.

    Args:
        team_identity: Must hold the Team private key.
        name: Membership name to record alongside its qualified Address.
        now: Override the current UTC issuance clock.
        ttl_seconds: Lifetime measured from issuance.

    Raises:
        ValueError: The Team key is absent or the Agent DID is not Ed25519.
    """
    if not team_identity.private_key:
        raise ValueError("Team private key not available for signing")
    if not is_ed25519_did_key(agent_did):
        raise ValueError("agent_did must be an Ed25519 did:key")
    instant = now or utc_now()
    iat = int(instant.timestamp())
    exp = int((instant + timedelta(seconds=int(ttl_seconds))).timestamp())
    payload: JsonObject = {
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
    """Verify a Team-signed statement and return its decoded membership claims.

    The expected Team DID must come from a source the caller trusts. This helper
    checks the signer, required claims and expiry; it does not grant Team access
    or check an expected audience or membership revocation.

    Args:
        team_did: Trusted expected issuer.
        now: Override the current UTC expiry clock.

    Raises:
        ValueError: The token, signer, required claims or expiry are invalid.
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
