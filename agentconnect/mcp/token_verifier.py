"""Verify MCP bearer tokens against Agent public keys.

Tokens are EdDSA JWTs minted by :meth:`BaseAgent.mint_mcp_access_token`.
The verifier loads the Agent public key from a registry entry identified
by the JWT ``sub`` claim.

This is the MCP door's credential check. Join authentication for the
Runtime lives in ``agentconnect.team.auth``.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from mcp.server.auth.provider import AccessToken, TokenVerifier

from agentconnect.core.identity import decode_eddsa_jwt, split_jwt
from agentconnect.index import RegistryAPIClient
from agentconnect.team.directory.registry_base import AgentRegistry


class MCPRegistryTokenVerifier(TokenVerifier):
    """Verify bearer tokens using Agent public keys from the registry.

    The token is an EdDSA JWT signed with the Agent's private key.
    """

    def __init__(
        self,
        registry: AgentRegistry | RegistryAPIClient,
        *,
        expected_audience: str | Sequence[str],
        issuer_url: str | None = None,
    ):
        """Bind the verifier to a registry and expected token audience."""
        self.registry = registry
        if isinstance(expected_audience, str):
            self.expected_audiences: List[str] = [expected_audience]
        else:
            self.expected_audiences = list(expected_audience)
        self.issuer_url = issuer_url
        self._logger = logging.getLogger(__name__)

    async def verify_token(self, token: str) -> Optional[AccessToken]:  # type: ignore[override]
        try:
            header, unverified_claims, _, _ = split_jwt(token)
        except Exception:
            self._logger.warning("Failed to parse JWT")
            return None
        if header.get("alg") != "EdDSA":
            self._logger.debug("JWT alg is not EdDSA")
            return None

        agent_id = unverified_claims.get("sub")
        aud_claim = unverified_claims.get("aud")
        jti = unverified_claims.get("jti")

        if not agent_id or not aud_claim or not jti:
            self._logger.debug(
                "JWT missing required claims sub/aud/jti: sub=%s aud=%s has_jti=%s",
                agent_id,
                aud_claim,
                bool(jti),
            )
            return None

        aud_list = aud_claim if isinstance(aud_claim, list) else [aud_claim]
        if not any(aud in self.expected_audiences for aud in aud_list):
            self._logger.debug(
                "JWT audience mismatch: aud_claims=%s expected_any=%s",
                aud_list,
                self.expected_audiences,
            )
            return None

        try:
            registration = await self.registry.get_registration(agent_id)
        except Exception:
            registration = None
        if registration is None:
            self._logger.debug("No registry entry for subject %s", agent_id)
            return None

        public_key_pem: str = registration.identity.public_key
        try:
            verified_claims = decode_eddsa_jwt(token, public_key_pem)
        except Exception as exc:
            self._logger.warning(
                "JWT signature/claims verification failed for sub=%s: %s",
                agent_id,
                exc,
            )
            return None

        iat = verified_claims.get("iat")
        exp = verified_claims.get("exp")
        if not isinstance(iat, int) or not isinstance(exp, int):
            return None
        import time as _time

        now = int(_time.time())
        if exp <= now:
            self._logger.debug("JWT expired for sub=%s", agent_id)
            return None

        if self.issuer_url is not None:
            iss_claim = verified_claims.get("iss")
            if iss_claim != self.issuer_url:
                self._logger.debug(
                    "JWT issuer mismatch: iss=%s expected=%s for sub=%s",
                    iss_claim,
                    self.issuer_url,
                    agent_id,
                )
                return None

        scopes: list[str] = []
        scope_claim = verified_claims.get("scope")
        if isinstance(scope_claim, str):
            for item in scope_claim.split():
                if item and item not in scopes:
                    scopes.append(item)
        scp_claim = verified_claims.get("scp")
        if isinstance(scp_claim, list):
            for item in scp_claim:
                text = str(item)
                if text and text not in scopes:
                    scopes.append(text)

        expires_at = exp if isinstance(exp, int) else None
        self._logger.debug(
            "JWT verified for sub=%s aud_ok=%s expires_at=%s",
            agent_id,
            True,
            expires_at,
        )
        return AccessToken(
            token=token, client_id=str(agent_id), scopes=scopes, expires_at=expires_at
        )
