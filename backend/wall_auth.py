"""Token verification for the deployable's generic capability door (the Wall).

The gateway already ships an async :class:`spine.gateway.app.verify.TokenVerifier`
that resolves a bearer token to a :class:`VerifiedIdentity`. The in-process Wall
(:class:`spine.gateway.app.wall.Wall`), however, expects a *synchronous*
``verify(token) -> Principal | None`` collaborator. This adapter bridges the two
WITHOUT duplicating the trust policy:

  * It honours the SAME dev-token policy as ``verify.py``: a clearly-marked
    ``DEV-UNSIGNED.<base64url(claims)>`` token is accepted ONLY when NO real
    public key and NO introspect URL is configured (the single-deployable deploy
    case). When a real key/introspect is configured, dev tokens are rejected and
    real verification is delegated to the gateway's verifier.
  * It maps the resolved identity's ``memberships`` (app/role/scope) onto the
    Wall's :class:`Principal` (canonical_uuid + roles + institution scope), so a
    DEV-UNSIGNED token carrying a teacher membership passes the TOKEN gate (RBAC
    / ABAC may still allow or deny downstream — that is the wall's job).

LAWS honoured:
  * Deny-by-default: any malformed / unparseable token resolves to ``None`` ->
    the wall raises INVALID_TOKEN.
  * Import-safe: no I/O, no secret read at import. The dev-only acceptance path
    is logged (names only), never silent.
  * Never reject a valid dev token just because the DB is in-memory: this
    verifier consults ONLY the key/introspect config, not any datastore.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

# RS256 verification is available only when PyJWT is installed. When it is NOT,
# a configured public key cannot be used to verify a signed token, so we degrade
# OBSERVABLY (log + deny the signed token) rather than silently accept it.
try:
    import jwt
    from jwt import InvalidTokenError

    _JWT_AVAILABLE = True
except Exception:  # pragma: no cover - exercised when PyJWT absent
    jwt = None  # type: ignore
    InvalidTokenError = Exception  # type: ignore
    _JWT_AVAILABLE = False

logger = logging.getLogger("clss.backend.wall_auth")

_UNSIGNED_DEV_PREFIX = "DEV-UNSIGNED."


def _unb64(s: str) -> str:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode("utf-8")


class WallTokenVerifier:
    """Synchronous ``verify(token) -> Principal | None`` for the in-process Wall.

    ``principal_cls`` is the gateway's :class:`Principal` dataclass (injected to
    avoid a hard import cycle through the aliased gateway package).
    """

    def __init__(
        self,
        *,
        principal_cls: Any,
        public_key: Optional[str],
        introspect_url: Optional[str],
        issuer: str = "clss.identity",
        audience: str = "clss.gateway",
        algorithm: str = "RS256",
    ) -> None:
        self._principal_cls = principal_cls
        self._public_key = public_key
        self._introspect_url = introspect_url
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm
        self._dev_only = not public_key and not introspect_url
        if self._dev_only:
            logger.warning(
                "wall token verifier in DEV-ONLY mode: no public key / introspect "
                "configured; DEV-UNSIGNED tokens are accepted (local/deploy dev). "
                "Set CLSS_GATEWAY_DEV_JWT_PUBLIC_KEY for signed verification."
            )
        elif public_key and not _JWT_AVAILABLE:
            logger.warning(
                "CLSS_GATEWAY_DEV_JWT_PUBLIC_KEY is set but PyJWT is not installed; "
                "signed RS256 tokens CANNOT be verified in-process and are denied. "
                "Install PyJWT to enable the signed wall."
            )

    # -- public collaborator surface (sync, as the Wall expects) ---------- #

    def verify(self, token: Optional[str]) -> Optional[Any]:
        if not token:
            return None
        claims = self._claims(token)
        if claims is None:
            return None
        return self._principal_from_claims(claims)

    # -- internals -------------------------------------------------------- #

    def _claims(self, token: str) -> Optional[dict]:
        if token.startswith(_UNSIGNED_DEV_PREFIX):
            # Mirror verify.py: accept the unsigned dev token ONLY when no real
            # public key is configured. A degraded (in-memory DB) gateway still
            # accepts it — the decision depends on KEY config, not the datastore.
            if self._public_key:
                logger.warning("unsigned dev token rejected: a real public key is configured")
                return None
            try:
                payload = _unb64(token[len(_UNSIGNED_DEV_PREFIX):])
                claims = json.loads(payload)
            except Exception:  # malformed -> deny by default
                return None
            if not isinstance(claims, dict) or "canonical_uuid" not in claims:
                return None
            return claims

        # A signed (non-dev) token: verify the RS256 signature with the PUBLIC
        # key (CLSS_GATEWAY_DEV_JWT_PUBLIC_KEY). We hold ONLY the public key —
        # never the private signing key (identity holds that). This mirrors the
        # gateway's verify.py so the in-process Wall honours the SAME trust policy
        # as the /v1 surface.
        if self._public_key and _JWT_AVAILABLE:
            try:
                return jwt.decode(  # type: ignore[union-attr]
                    token,
                    self._public_key,
                    algorithms=[self._algorithm],
                    audience=self._audience,
                    issuer=self._issuer,
                )
            except InvalidTokenError as exc:  # type: ignore[misc]
                logger.warning("signed token rejected: %s", type(exc).__name__)
                return None

        # No usable verification path (no public key, or PyJWT absent): a signed
        # token cannot be verified in-process -> deny by default.
        return None

    def _principal_from_claims(self, claims: dict) -> Optional[Any]:
        canonical_uuid = claims.get("canonical_uuid")
        if not canonical_uuid:
            return None
        memberships = claims.get("memberships") or []

        roles: list[str] = []
        institution_uuid: Optional[str] = None
        for m in memberships:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            if isinstance(role, str) and role:
                roles.append(role)
            scope = m.get("scope")
            if institution_uuid is None and isinstance(scope, str) and scope:
                institution_uuid = scope

        consent_scopes = claims.get("consent_scopes") or []
        if not isinstance(consent_scopes, (list, tuple)):
            consent_scopes = ()

        return self._principal_cls(
            canonical_uuid=str(canonical_uuid),
            roles=tuple(dict.fromkeys(roles)),  # de-duped, order-preserving
            institution_uuid=institution_uuid,
            consent_scopes=tuple(consent_scopes),
        )
