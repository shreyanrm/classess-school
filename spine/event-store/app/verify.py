"""Token verification (defense in depth).

The event store sits behind the gateway, but it never trusts an unauthenticated
caller (INVARIANT 3). It verifies the identity token with the PUBLIC key only
(RS256), never holding the private signing key. A clearly-marked unsigned dev
token is accepted only when no public key is configured.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

logger = logging.getLogger("clss.eventstore.verify")

try:
    import jwt
    from jwt import InvalidTokenError

    _JWT_AVAILABLE = True
except Exception:  # pragma: no cover
    jwt = None  # type: ignore
    InvalidTokenError = Exception  # type: ignore
    _JWT_AVAILABLE = False

_UNSIGNED_DEV_PREFIX = "DEV-UNSIGNED."


class VerificationError(RuntimeError):
    pass


class TokenVerifier:
    def __init__(self, *, public_key: str | None, issuer: str, audience: str, algorithm: str) -> None:
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm

    def verify(self, token: str) -> dict:
        if token.startswith(_UNSIGNED_DEV_PREFIX):
            if self._public_key:
                raise VerificationError("unsigned dev token rejected: a real public key is configured")
            logger.warning("accepting UNSIGNED DEV token — local dev only.")
            return json.loads(_unb64(token[len(_UNSIGNED_DEV_PREFIX):]))
        if not self._public_key or not _JWT_AVAILABLE:
            raise VerificationError(
                "no verification key configured. Set clss.eventstore.dev.jwt_public_key."
            )
        try:
            return jwt.decode(  # type: ignore[union-attr]
                token, self._public_key, algorithms=[self._algorithm],
                audience=self._audience, issuer=self._issuer,
            )
        except InvalidTokenError as exc:  # type: ignore[misc]
            raise VerificationError(f"invalid token: {exc}") from exc


def _unb64(s: str) -> str:
    import base64
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode()
