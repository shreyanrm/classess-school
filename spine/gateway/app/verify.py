"""Token verification at the wall.

The gateway verifies the identity token with the PUBLIC key (RS256) only — it
never holds the private signing key (INVARIANT 4). If no public key is
configured it falls back to calling the identity service's introspect endpoint.
If neither is available it refuses every request (deny by default), naming the
env var to set.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import httpx

from .models import Membership, VerifiedIdentity

try:
    import jwt
    from jwt import InvalidTokenError

    _JWT_AVAILABLE = True
except Exception:  # pragma: no cover
    jwt = None  # type: ignore
    InvalidTokenError = Exception  # type: ignore
    _JWT_AVAILABLE = False

logger = logging.getLogger("clss.gateway.verify")

_UNSIGNED_DEV_PREFIX = "DEV-UNSIGNED."


class VerificationError(RuntimeError):
    pass


class TokenVerifier:
    def __init__(
        self,
        *,
        public_key: str | None,
        issuer: str,
        audience: str,
        algorithm: str,
        introspect_url: str | None,
    ) -> None:
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm
        self._introspect_url = introspect_url

    async def verify(self, token: str) -> VerifiedIdentity:
        claims = await self._claims(token)
        return VerifiedIdentity(
            canonical_uuid=UUID(claims["canonical_uuid"]),
            app=claims["app"],
            memberships=[Membership(**m) for m in claims.get("memberships", [])],
        )

    async def _claims(self, token: str) -> dict:
        # Local-dev unsigned token (clearly marked). Accept only when no real
        # public key is configured, mirroring the identity service.
        if token.startswith(_UNSIGNED_DEV_PREFIX):
            if self._public_key:
                raise VerificationError("unsigned dev token rejected: a real public key is configured")
            logger.warning("accepting UNSIGNED DEV token — local dev only.")
            return json.loads(_unb64(token[len(_UNSIGNED_DEV_PREFIX):]))

        if self._public_key and _JWT_AVAILABLE:
            try:
                return jwt.decode(  # type: ignore[union-attr]
                    token, self._public_key, algorithms=[self._algorithm],
                    audience=self._audience, issuer=self._issuer,
                )
            except InvalidTokenError as exc:  # type: ignore[misc]
                raise VerificationError(f"invalid token: {exc}") from exc

        if self._introspect_url:
            return await self._introspect(token)

        raise VerificationError(
            "no verification path configured. Set clss.gateway.dev.jwt_public_key "
            "or clss.gateway.dev.identity_introspect_url."
        )

    async def _introspect(self, token: str) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                self._introspect_url,  # type: ignore[arg-type]
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            raise VerificationError("identity introspection rejected the token")
        data = resp.json()
        # Normalize introspect response shape to claims used here.
        return {
            "canonical_uuid": data["canonical_uuid"],
            "app": data["app"],
            "memberships": data.get("memberships", []),
            "exp": data.get("expires_at"),
        }


def _unb64(s: str) -> str:
    import base64
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode()
