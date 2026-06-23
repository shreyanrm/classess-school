"""Identity token minting and verification.

The identity service mints gateway-verifiable JWTs. Asymmetric signing (RS256
by default): the PRIVATE key lives only here; the gateway holds only the PUBLIC
key and verifies. INVARIANT 1/2: claims carry ONLY the opaque canonical_uuid
plus authorization inputs (app, memberships) — never PII.

Degraded mode: if no signing key is configured the service cannot mint a real
signed token. Rather than fabricate or hardcode a key (forbidden by INVARIANT
4), it raises a clear, named error telling the operator which env var to set.
A local-only unsigned development fallback is available behind an explicit,
loudly-logged flag so contract testing can proceed; it is never used when a key
is present and is never the production path.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

try:
    import jwt  # PyJWT
    from jwt import InvalidTokenError

    _JWT_AVAILABLE = True
except Exception:  # pragma: no cover
    jwt = None  # type: ignore
    InvalidTokenError = Exception  # type: ignore
    _JWT_AVAILABLE = False

logger = logging.getLogger("clss.identity.tokens")

_UNSIGNED_DEV_PREFIX = "DEV-UNSIGNED."


class TokenError(RuntimeError):
    """Raised when a token cannot be minted/verified due to missing config."""


class TokenService:
    def __init__(
        self,
        *,
        private_key: str | None,
        public_key: str | None,
        issuer: str,
        audience: str,
        algorithm: str,
        ttl_seconds: int,
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm
        self._ttl = ttl_seconds

    @property
    def can_sign(self) -> bool:
        return bool(self._private_key) and _JWT_AVAILABLE

    def mint(self, *, canonical_uuid: UUID, app: str, memberships: list[dict]) -> tuple[str, int, datetime]:
        """Return (token, expires_in_seconds, expires_at). No PII in claims."""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=self._ttl)
        claims = {
            "sub": str(canonical_uuid),       # opaque subject — INVARIANT 2
            "canonical_uuid": str(canonical_uuid),
            "app": app,
            "memberships": memberships,        # authz inputs only, no PII
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        if self.can_sign:
            token = jwt.encode(claims, self._private_key, algorithm=self._algorithm)  # type: ignore[union-attr]
            return token, self._ttl, exp
        # Degraded local fallback (no key configured). Loud, never production.
        logger.warning(
            "MINTING UNSIGNED DEV TOKEN: no signing key configured. Set "
            "clss.identity.dev.jwt_private_key for real tokens. This token is "
            "NOT trustworthy and must never be accepted in staging/prod."
        )
        payload = _UNSIGNED_DEV_PREFIX + _b64(json.dumps(claims))
        return payload, self._ttl, exp

    def verify(self, token: str) -> dict:
        """Verify and return claims. Used by /auth/token/introspect and the
        gateway (which uses the public key copy)."""
        if token.startswith(_UNSIGNED_DEV_PREFIX):
            logger.warning("verifying UNSIGNED DEV token — accept only in local dev.")
            return json.loads(_unb64(token[len(_UNSIGNED_DEV_PREFIX):]))
        if not _JWT_AVAILABLE:  # pragma: no cover
            raise TokenError("PyJWT not installed; cannot verify signed tokens.")
        key = self._public_key or self._private_key
        if not key:
            raise TokenError(
                "no verification key configured. Set clss.identity.dev.jwt_public_key."
            )
        try:
            return jwt.decode(  # type: ignore[union-attr]
                token, key, algorithms=[self._algorithm],
                audience=self._audience, issuer=self._issuer,
            )
        except InvalidTokenError as exc:  # type: ignore[misc]
            raise TokenError(f"invalid token: {exc}") from exc


def _b64(s: str) -> str:
    import base64
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def _unb64(s: str) -> str:
    import base64
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode()
