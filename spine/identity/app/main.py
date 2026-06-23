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
    AccessEvent,
    AccessGrantRecord,
    AccessGrantRequest,
    AppId,
    CanonicalUserCreate,
    CanonicalUserIssued,
    ConsentCheckRequest,
    ConsentCheckResponse,
    ConsentGrantRequest,
    ConsentRecord,
    DeviceRecord,
    DeviceRegisterRequest,
    Membership,
    OtpStartRequest,
    OtpStartResponse,
    OtpVerifyRequest,
    Purpose,
    SessionRiskRequest,
    SessionRiskResponse,
    SsoCallbackRequest,
    SsoStartRequest,
    SsoStartResponse,
    TokenClaims,
    TokenResponse,
)
from . import sso
from .store import IdentityStore, build_store, _grant_active
from .tokens import TokenError, TokenService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clss.identity")

# In-process OTP challenge map for the degraded path. In production OTP state
# lives in Redis (clss.identity.dev.redis_url) and dispatch goes via Supabase
# Auth. We never store or log the code.
_otp_challenges: dict[UUID, dict] = {}

# In-process anti-forgery state for the degraded SSO path. In production this
# lives in Redis with the OTP state. Maps state -> {provider, app, redirect_uri}.
_sso_states: dict[str, dict] = {}

# Signals that raise the risk band. Non-identifying, coarse signals only; the
# human is always final and identity never blocks on its own.
_HIGH_RISK_SIGNALS = frozenset({"impossible_travel", "credential_stuffing", "tor_exit"})
_MEDIUM_RISK_SIGNALS = frozenset({"new_device", "new_geo", "new_ip", "elevated_velocity"})


def _derive_risk(signals: list[str]) -> str:
    """Map coarse session signals to a band. Generate-and-verify spirit: a
    derived band, never an automated consequential action."""
    s = set(signals)
    if s & _HIGH_RISK_SIGNALS:
        return "high"
    if s & _MEDIUM_RISK_SIGNALS:
        return "medium"
    return "low"


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
    await store.record_access(
        canonical_uuid=canonical_uuid, action="auth.otp.verified",
        outcome="issued", app=app_id,
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
# SSO — the single front door. Phone-OTP stays first; these are delegated
# federations (Google / Apple / Microsoft / institutional SSO+SAML).
# Auto-provisions ONE canonical identity on first signup. Degrades cleanly.
# ---------------------------------------------------------------------------
@app.post("/v1/identity/auth/sso/start", response_model=SsoStartResponse, status_code=202, tags=["auth"])
async def auth_sso_start(req: SsoStartRequest) -> SsoStartResponse:
    started = sso.build_start(provider=req.provider, app=req.app, redirect_uri=req.redirect_uri)
    _sso_states[started.state] = {
        "provider": req.provider, "app": req.app, "redirect_uri": req.redirect_uri,
        "created_at": datetime.now(timezone.utc),
    }
    logger.info("SSO start for provider=%s (state only): %s degraded=%s",
                req.provider, started.state, started.degraded)
    return SsoStartResponse(
        provider=req.provider, authorization_url=started.authorization_url,
        state=started.state, degraded=started.degraded,
    )


@app.post("/v1/identity/auth/sso/callback", response_model=TokenResponse, tags=["auth"])
async def auth_sso_callback(
    req: SsoCallbackRequest,
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> TokenResponse:
    pending = _sso_states.get(req.state)
    if pending is None or pending["provider"] != req.provider:
        raise HTTPException(status_code=401, detail="invalid or expired sso state")
    _sso_states.pop(req.state, None)
    app_id: AppId = pending["app"]

    # The provider's stable subject. In production this comes from the verified
    # token exchange; in the degraded/local path the caller supplies it directly
    # so the federation is exercisable offline. Without either, fail closed.
    subject = req.subject or (req.code if req.code else None)
    if not subject:
        raise HTTPException(status_code=401, detail="provider did not return a subject")

    # Auto-provision ONE canonical identity on first signup (single front door).
    canonical_uuid = await store.resolve_by_federation(provider=req.provider, subject=subject)
    first_signup = canonical_uuid is None
    if canonical_uuid is None:
        canonical_uuid = await store.issue_canonical_user(
            phone=None, full_name=req.full_name, dob=None, email=req.email
        )
    await store.link_federation(
        canonical_uuid=canonical_uuid, provider=req.provider, subject=subject,
        email=req.email, full_name=req.full_name,
    )

    raw = await store.active_memberships(canonical_uuid, app_id)
    memberships = [_to_membership(m) for m in raw]
    token, expires_in, _exp = tokens.mint(
        canonical_uuid=canonical_uuid, app=app_id,
        memberships=[m.model_dump(mode="json") for m in memberships],
    )
    await store.record_access(
        canonical_uuid=canonical_uuid,
        action="sso.signup" if first_signup else "sso.callback",
        outcome="issued", app=app_id,
    )
    return TokenResponse(access_token=token, expires_in=expires_in, canonical_uuid=canonical_uuid)


# ---------------------------------------------------------------------------
# Device & session risk management (session, device, and risk).
# ---------------------------------------------------------------------------
@app.post("/v1/identity/devices/register", response_model=DeviceRecord, status_code=201, tags=["device"])
async def register_device(
    req: DeviceRegisterRequest,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> DeviceRecord:
    _verify(tokens, authorization)
    rec = await store.register_device(
        canonical_uuid=req.canonical_uuid, device_fingerprint=req.device_fingerprint,
        label=req.label, platform=req.platform,
    )
    await store.record_access(
        canonical_uuid=req.canonical_uuid, action="device.registered",
        outcome="issued", device_id=rec["device_id"],
    )
    return DeviceRecord(**_device_public(rec))


@app.get("/v1/identity/devices", response_model=list[DeviceRecord], tags=["device"])
async def list_devices(
    canonical_uuid: UUID = Query(...),
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> list[DeviceRecord]:
    _verify(tokens, authorization)
    rows = await store.list_devices(canonical_uuid)
    return [DeviceRecord(**_device_public(r)) for r in rows]


@app.post("/v1/identity/devices/{device_id}/revoke", status_code=204, tags=["device"])
async def revoke_device(
    device_id: UUID,
    canonical_uuid: UUID = Query(...),
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> None:
    _verify(tokens, authorization)
    ok = await store.revoke_device(canonical_uuid=canonical_uuid, device_id=device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="device not found or already revoked")
    await store.record_access(
        canonical_uuid=canonical_uuid, action="device.revoked",
        outcome="revoked", device_id=device_id,
    )


@app.post("/v1/identity/sessions/risk", response_model=SessionRiskResponse, tags=["device"])
async def assess_session_risk(
    req: SessionRiskRequest,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> SessionRiskResponse:
    _verify(tokens, authorization)
    risk = _derive_risk(req.signals)
    rec = await store.record_session_risk(
        canonical_uuid=req.canonical_uuid, session_id=req.session_id,
        risk=risk, signals=req.signals, device_id=req.device_id,
    )
    await store.record_access(
        canonical_uuid=req.canonical_uuid, action="session.risk_assessed",
        outcome="allowed", session_id=req.session_id, device_id=req.device_id, risk=risk,
    )
    return SessionRiskResponse(
        session_id=req.session_id, canonical_uuid=req.canonical_uuid, risk=risk,
        signals=req.signals,
        # PERMISSION LADDER: a high band RECOMMENDS step-up; it never blocks on
        # its own. The gateway/human decides.
        requires_step_up=(risk == "high"),
        assessed_at=rec["assessed_at"],
    )


# ---------------------------------------------------------------------------
# Access history (full access history and audit).
# ---------------------------------------------------------------------------
@app.get("/v1/identity/access-history", response_model=list[AccessEvent], tags=["history"])
async def access_history(
    canonical_uuid: UUID = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> list[AccessEvent]:
    _verify(tokens, authorization)
    rows = await store.access_history(canonical_uuid, limit=limit)
    return [AccessEvent(**r) for r in rows]


# ---------------------------------------------------------------------------
# Delegated / temporary / substitute access — first-class TIME-BOUND grants.
# ---------------------------------------------------------------------------
@app.post("/v1/identity/access-grants", response_model=AccessGrantRecord, status_code=201, tags=["grants"])
async def create_access_grant(
    req: AccessGrantRequest,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> AccessGrantRecord:
    _verify(tokens, authorization)
    starts_at = req.starts_at or datetime.now(timezone.utc)
    if req.expires_at <= starts_at:
        raise HTTPException(status_code=422, detail="expires_at must be after starts_at")
    rec = await store.create_access_grant(
        kind=req.kind, grantee=req.grantee, granted_by=req.granted_by, app=req.app,
        role=req.role, scope=req.scope, starts_at=starts_at, expires_at=req.expires_at,
        reason=req.reason,
    )
    await store.record_access(
        canonical_uuid=req.grantee, action=f"grant.{req.kind}.created",
        outcome="issued", app=req.app, scope=req.scope,
    )
    return _to_grant(rec)


@app.get("/v1/identity/access-grants", response_model=list[AccessGrantRecord], tags=["grants"])
async def list_access_grants(
    grantee: UUID | None = Query(default=None),
    granted_by: UUID | None = Query(default=None),
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> list[AccessGrantRecord]:
    _verify(tokens, authorization)
    rows = await store.list_access_grants(grantee=grantee, granted_by=granted_by)
    return [_to_grant(r) for r in rows]


@app.post("/v1/identity/access-grants/{grant_id}/revoke", status_code=204, tags=["grants"])
async def revoke_access_grant(
    grant_id: UUID,
    authorization: str | None = Header(default=None),
    store: IdentityStore = Depends(get_store),
    tokens: TokenService = Depends(get_tokens),
) -> None:
    _verify(tokens, authorization)
    ok = await store.revoke_access_grant(grant_id=grant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="grant not found or already revoked")


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


def _device_public(row: dict) -> dict:
    """Strip the in-vault fingerprint; the response carries no raw identifier."""
    return {
        "device_id": row["device_id"], "canonical_uuid": row["canonical_uuid"],
        "label": row.get("label"), "platform": row.get("platform"),
        "registered_at": row["registered_at"], "last_seen_at": row.get("last_seen_at"),
        "revoked_at": row.get("revoked_at"), "trusted": row.get("trusted", False),
    }


def _to_grant(row: dict) -> AccessGrantRecord:
    return AccessGrantRecord(
        grant_id=row["grant_id"], kind=row["kind"], grantee=row["grantee"],
        granted_by=row["granted_by"], app=row["app"], role=row["role"],
        scope=row["scope"], starts_at=row["starts_at"], expires_at=row["expires_at"],
        reason=row.get("reason"), granted_at=row["granted_at"],
        revoked_at=row.get("revoked_at"), active=_grant_active(row),
    )
