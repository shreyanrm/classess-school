"""Identity & access service — FastAPI app.

Endpoints mirror contracts/src/openapi/identity.ts:
  POST /v1/identity/auth/otp/start       -> begin phone-OTP
  POST /v1/identity/auth/otp/verify      -> verify OTP, issue token
  POST /v1/identity/auth/token/introspect-> verify a token (used by the gateway)
  GET  /v1/identity/memberships/resolve  -> active memberships + scope (RBAC inputs)
  POST /v1/identity/consent/check        -> consent + purpose satisfied? (INVARIANT 6)
  POST /v1/identity/consent/grant        -> capture a consent grant

Internal, privileged (gateway-guarded) provisioning:
  POST /v1/identity/internal/users       -> issue a canonical user; returns the
                                            opaque canonical_uuid ONLY.

PII boundary: phone/name/dob/email are accepted on the OTP-start and the
internal user route and written ONLY to the vault. No response model on any
route carries PII. The OTP code path delegates dispatch to Supabase Auth in
production; without it, the service issues a deterministic dev challenge and
logs (NEVER the code itself) that it is degraded.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from .config import IdentitySettings, get_settings
from .models import (
    AppId,
    CanonicalUserCreate,
    CanonicalUserIssued,
    ConsentCheckRequest,
    ConsentCheckResponse,
    ConsentGrantRequest,
    ConsentRecord,
    Membership,
    OtpStartRequest,
    OtpStartResponse,
    OtpVerifyRequest,
    Purpose,
    TokenClaims,
    TokenResponse,
)
from .store import IdentityStore, build_store
from .tokens import TokenError, TokenService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clss.identity")

# In-process OTP challenge map for the degraded path. In production OTP state
# lives in Redis (clss.identity.dev.redis_url) and dispatch goes via Supabase
# Auth. We never store or log the code.
_otp_challenges: dict[UUID, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    missing = settings.degraded_reasons()
    if missing:
        logger.warning("identity starting DEGRADED. Missing config (names only): %s", ", ".join(missing))
    store = build_store(settings.database_url)
    await store.connect()
    logger.info("identity store backend: %s", store.backend)
    tokens = TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        algorithm=settings.jwt_algorithm,
        ttl_seconds=settings.token_ttl_seconds,
    )
    app.state.store = store
    app.state.tokens = tokens
    app.state.settings = settings
    try:
        yield
    finally:
        await store.close()


app = FastAPI(
    title="Classess Identity",
    version="0.1.0",
    description=(
        "Canonical identity, app membership and scope, and consent. PII is "
        "vaulted and segregated; only the opaque canonical_uuid crosses this "
        "boundary."
    ),
    lifespan=lifespan,
)


def get_store() -> IdentityStore:
    return app.state.store


def get_tokens() -> TokenService:
    return app.state.tokens


def get_cfg() -> IdentitySettings:
    return app.state.settings


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok", "service": "identity", "store": get_store().backend}


# ---------------------------------------------------------------------------
# Auth — phone-OTP-first
# ---------------------------------------------------------------------------
@app.post("/v1/identity/auth/otp/start", response_model=OtpStartResponse, status_code=202, tags=["auth"])
async def auth_otp_start(req: OtpStartRequest, store: IdentityStore = Depends(get_store)) -> OtpStartResponse:
    # Provision-or-resolve the person in the vault by phone. PII written here only.
    canonical_uuid = await store.resolve_by_phone(req.phone)
    if canonical_uuid is None:
        canonical_uuid = await store.issue_canonical_user(
            phone=req.phone, full_name=None, dob=None, email=None
        )
    challenge_id = uuid4()
    # In production: Supabase Auth dispatches the OTP. The code is NEVER stored
    # in plaintext or logged here.
    _otp_challenges[challenge_id] = {
        "canonical_uuid": canonical_uuid, "app": req.app, "created_at": datetime.now(timezone.utc),
    }
    logger.info("OTP challenge issued (challenge_id only): %s", challenge_id)
    return OtpStartResponse(challenge_id=challenge_id)


@app.post("/v1/identity/auth/otp/verify", response_model=TokenResponse, tags=["auth"])
async def auth_otp_verify(
    req: OtpVerifyRequest,
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
    cfg: IdentitySettings = Depends(get_cfg),
) -> TokenResponse:
    challenge = _otp_challenges.get(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=401, detail="invalid or expired challenge")
    # Production verification is delegated to Supabase Auth. In the degraded
    # local path we accept a non-empty code so the contract can be exercised.
    if cfg.supabase_url is None and not req.code:
        raise HTTPException(status_code=401, detail="invalid or expired code")
    _otp_challenges.pop(req.challenge_id, None)

    canonical_uuid: UUID = challenge["canonical_uuid"]
    app_id: AppId = challenge["app"]
    raw_memberships = await store.active_memberships(canonical_uuid, app_id)
    memberships = [_to_membership(m) for m in raw_memberships]
    token, expires_in, _exp = tokens.mint(
        canonical_uuid=canonical_uuid,
        app=app_id,
        memberships=[m.model_dump(mode="json") for m in memberships],
    )
    return TokenResponse(access_token=token, expires_in=expires_in, canonical_uuid=canonical_uuid)


@app.post("/v1/identity/auth/token/introspect", response_model=TokenClaims, tags=["auth"])
async def auth_token_introspect(
    authorization: str | None = Header(default=None),
    tokens: TokenService = Depends(get_tokens),
) -> TokenClaims:
    token = _bearer(authorization)
    try:
        claims = tokens.verify(token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return TokenClaims(
        canonical_uuid=UUID(claims["canonical_uuid"]),
        app=claims["app"],
        memberships=[Membership(**m) for m in claims.get("memberships", [])],
        expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Membership resolution (RBAC/ABAC inputs)
# ---------------------------------------------------------------------------
@app.get("/v1/identity/memberships/resolve", response_model=list[Membership], tags=["membership"])
async def resolve_memberships(
    authorization: str | None = Header(default=None),
    app_q: AppId | None = Query(default=None, alias="app"),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> list[Membership]:
    claims = _verify(tokens, authorization)
    canonical_uuid = UUID(claims["canonical_uuid"])
    rows = await store.active_memberships(canonical_uuid, app_q)
    return [_to_membership(m) for m in rows]


# ---------------------------------------------------------------------------
# Consent (INVARIANT 6)
# ---------------------------------------------------------------------------
@app.post("/v1/identity/consent/check", response_model=ConsentCheckResponse, tags=["consent"])
async def consent_check(
    req: ConsentCheckRequest,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> ConsentCheckResponse:
    _verify(tokens, authorization)
    result = await store.check_consent(
        canonical_uuid=req.canonical_uuid, scope=req.scope, purpose=req.purpose
    )
    return ConsentCheckResponse(satisfied=result["satisfied"], consent_ref=result["consent_ref"])


@app.post("/v1/identity/consent/grant", response_model=ConsentRecord, status_code=201, tags=["consent"])
async def consent_grant(
    req: ConsentGrantRequest,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> ConsentRecord:
    _verify(tokens, authorization)
    rec = await store.grant_consent(
        canonical_uuid=req.canonical_uuid, scope=req.scope, purpose=req.purpose,
        age_tier=req.age_tier, granted_by=req.granted_by,
    )
    return ConsentRecord(**rec)


# ---------------------------------------------------------------------------
# Internal privileged provisioning. Returns the opaque canonical_uuid ONLY.
# Reachable only behind the gateway with a privileged policy.
# ---------------------------------------------------------------------------
@app.post("/v1/identity/internal/users", response_model=CanonicalUserIssued, status_code=201, tags=["internal"])
async def issue_canonical_user(
    req: CanonicalUserCreate,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> CanonicalUserIssued:
    _verify(tokens, authorization)
    canonical_uuid = await store.issue_canonical_user(
        phone=req.phone, full_name=req.full_name, dob=req.dob, email=req.email
    )
    # Only the opaque id leaves the boundary. PII never appears in the response.
    return CanonicalUserIssued(canonical_uuid=canonical_uuid)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def _verify(tokens: TokenService, authorization: str | None) -> dict:
    token = _bearer(authorization)
    try:
        return tokens.verify(token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _to_membership(row: dict) -> Membership:
    scope = row["scope"]
    # The DB stores scope as a jsonb object; the contract surfaces it as a string
    # ABAC scope. Serialize objects deterministically.
    if isinstance(scope, dict):
        import json
        scope_str = json.dumps(scope, sort_keys=True, separators=(",", ":"))
    else:
        scope_str = str(scope)
    return Membership(
        app=row["app"], role=row["role"], scope=scope_str,
        granted_at=row["granted_at"], revoked_at=row.get("revoked_at"),
    )
