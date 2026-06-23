"""Pydantic mirrors of the identity contract (contracts/src/openapi/identity.ts).

These shapes are the single source of truth that the developer lanes bind to.
They carry ONLY the opaque canonical_uuid and non-identifying authorization
inputs across the boundary; PII (phone, name, dob, email) never appears in a
response model, only in the vault-write request model that stays inside this
service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Closed enums mirrored from contracts/src/events/primitives.ts and the
# identity OpenAPI spec.
AppId = Literal["school", "learner", "platform"]
# The institution's control surface is role-scoped (classess-school.html §0,§8):
# owner/principal as admin, plus the distinct operational roles. Each role is an
# authorization input only; *where* and *for whom* is governed by ABAC scope.
Role = Literal[
    "admin",
    "teacher",
    "student",
    "parent",
    "coordinator",
    "hod",
    "examination",
    "support",
    "it",
]

# Provider identifiers for the single-front-door SSO. Phone-OTP stays first;
# these are delegated federations that auto-provision one canonical identity on
# first signup. "saml" is institutional SSO (any SAML/OIDC IdP).
SsoProvider = Literal["google", "apple", "microsoft", "saml"]

# Time-bound grant kinds (classess-school.html §8: "Delegated, temporary, and
# substitute access are first-class").
GrantKind = Literal["delegated", "temporary", "substitute"]

# Coarse risk bands for a session/device. Never punitive on their own; an input
# to the gateway and to step-up decisions.
RiskLevel = Literal["low", "medium", "high"]
Purpose = Literal[
    "instruction",
    "assessment",
    "mastery",
    "intervention",
    "operations",
    "communication",
    "account",
]
AgeTier = Literal["child", "teen", "adult"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Auth — phone-OTP-first (Supabase Auth is the mechanism).
# ---------------------------------------------------------------------------
class OtpStartRequest(_Strict):
    phone: str = Field(description="E.164 phone. Handled inside the vault boundary; never logged.")
    app: AppId


class OtpStartResponse(_Strict):
    challenge_id: UUID


class OtpVerifyRequest(_Strict):
    challenge_id: UUID
    code: str


class Membership(_Strict):
    """RBAC/ABAC inputs the gateway evaluates. Time-bound; no PII."""

    app: AppId
    role: Role
    scope: str = Field(description="ABAC scope, e.g. institution/grade/section identifiers.")
    granted_at: datetime
    revoked_at: datetime | None = None


class TokenResponse(_Strict):
    access_token: str = Field(description="Gateway-verifiable JWT. No PII in claims.")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    canonical_uuid: UUID = Field(description="Opaque identity ref (INVARIANT 1, 2).")


class TokenClaims(_Strict):
    """Decoded token claims. Opaque canonical_uuid + authz inputs only, never PII."""

    canonical_uuid: UUID
    app: AppId
    memberships: list[Membership] = Field(default_factory=list)
    expires_at: datetime


# ---------------------------------------------------------------------------
# Consent (INVARIANT 6).
# ---------------------------------------------------------------------------
class ConsentCheckRequest(_Strict):
    canonical_uuid: UUID
    scope: str
    purpose: Purpose


class ConsentCheckResponse(_Strict):
    satisfied: bool
    consent_ref: UUID | None = None


class ConsentGrantRequest(_Strict):
    canonical_uuid: UUID
    scope: str
    purpose: Purpose
    age_tier: AgeTier
    granted_by: UUID = Field(description="Opaque ref: self, or guardian for a child/teen.")


class ConsentRecord(_Strict):
    consent_id: UUID
    canonical_uuid: UUID
    scope: str
    purpose: Purpose
    age_tier: AgeTier
    granted_by: UUID
    granted_at: datetime
    revoked_at: datetime | None = None


# ---------------------------------------------------------------------------
# Vault write (INSIDE the boundary only — PII present, never returned).
# This model is accepted on a privileged, gateway-guarded internal route used
# to provision a canonical user. The response is the opaque canonical_uuid ONLY.
# ---------------------------------------------------------------------------
class CanonicalUserCreate(_Strict):
    phone: str | None = None
    full_name: str | None = None
    dob: str | None = Field(default=None, description="ISO date; drives age-tier derivation.")
    email: str | None = None


class CanonicalUserIssued(_Strict):
    """The ONLY thing that leaves the vault: the opaque, random canonical_uuid."""

    canonical_uuid: UUID = Field(description="Random/opaque. Never derived from PII (INVARIANT 2).")


# ---------------------------------------------------------------------------
# SSO — the single front door (classess-school.html §0, §8).
# Phone-OTP stays first; these are delegated federations. The flow: start ->
# (provider) -> callback. On first callback for a subject the service
# auto-provisions ONE canonical identity. Degrades cleanly with no provider
# config: start returns a clearly-labelled local dev authorization URL and the
# callback still issues a token so the contract is exercisable offline.
# ---------------------------------------------------------------------------
class SsoStartRequest(_Strict):
    provider: SsoProvider
    app: AppId
    # Where the provider should send the user back. Echoed, never trusted blindly.
    redirect_uri: str | None = None


class SsoStartResponse(_Strict):
    provider: SsoProvider
    # The provider's authorization URL the client redirects to. In degraded mode
    # this is a clearly-labelled local dev URL.
    authorization_url: str
    # Opaque anti-forgery value the client must echo back to the callback.
    state: str
    # True when no real provider is configured (degraded/offline path).
    degraded: bool = False


class SsoCallbackRequest(_Strict):
    provider: SsoProvider
    state: str = Field(description="The anti-forgery value from /sso/start.")
    # The provider's authorization code (degraded mode accepts a dev marker).
    code: str | None = None
    # The provider's stable subject id (degraded/local mode supplies it directly
    # so the federation can be exercised offline). Treated as opaque, vaulted.
    subject: str | None = None
    # Optional verified email/name from the provider; vaulted, never returned.
    email: str | None = None
    full_name: str | None = None


# ---------------------------------------------------------------------------
# Device & session risk management (classess-school.html §8: "session, device,
# and risk"). Devices and sessions carry NO PII — opaque ids and coarse signals.
# ---------------------------------------------------------------------------
class DeviceRegisterRequest(_Strict):
    canonical_uuid: UUID
    # Caller-supplied opaque fingerprint (hash). Never a raw identifier/PII.
    device_fingerprint: str = Field(description="Opaque device hash. No PII.")
    # Non-identifying, human-set label (e.g. 'classroom tablet'); optional.
    label: str | None = None
    platform: str | None = Field(default=None, description="Coarse platform hint, e.g. 'web'/'android'.")


class DeviceRecord(_Strict):
    device_id: UUID
    canonical_uuid: UUID
    label: str | None = None
    platform: str | None = None
    registered_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
    trusted: bool = False


class SessionRiskRequest(_Strict):
    canonical_uuid: UUID
    session_id: UUID
    # Coarse, non-identifying signals only (e.g. 'new_device', 'impossible_travel',
    # 'tor_exit'). Used to derive a band; the human is always final.
    signals: list[str] = Field(default_factory=list)
    device_id: UUID | None = None


class SessionRiskResponse(_Strict):
    session_id: UUID
    canonical_uuid: UUID
    risk: RiskLevel
    signals: list[str] = Field(default_factory=list)
    # When high, the gateway should require step-up; identity never blocks alone.
    requires_step_up: bool = False
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Access history (classess-school.html §8: "full access history and audit").
# Opaque canonical_uuid + non-identifying action/scope/outcome only.
# ---------------------------------------------------------------------------
class AccessEvent(_Strict):
    event_id: UUID
    canonical_uuid: UUID
    action: str = Field(description="e.g. 'auth.otp.verified', 'sso.callback', 'device.registered'.")
    app: AppId | None = None
    scope: str | None = None
    outcome: Literal["allowed", "denied", "issued", "revoked"]
    occurred_at: datetime
    device_id: UUID | None = None
    session_id: UUID | None = None
    risk: RiskLevel | None = None


# ---------------------------------------------------------------------------
# Delegated / temporary / substitute access — first-class TIME-BOUND grants
# (classess-school.html §8, §9 substitution ladder Level 5). A grant produces a
# real membership for the grantee, bounded by [starts_at, expires_at], that the
# resolver and the gateway treat exactly like any other membership but which is
# automatically inactive outside its window and revocable immediately.
# ---------------------------------------------------------------------------
class AccessGrantRequest(_Strict):
    kind: GrantKind
    # The identity that receives the access (e.g. the substitute teacher).
    grantee: UUID
    # The identity authorising it (e.g. a coordinator/HOD). Recorded for audit.
    granted_by: UUID
    app: AppId
    role: Role
    scope: str = Field(description="ABAC scope the grant is limited to, e.g. a grade/section.")
    expires_at: datetime = Field(description="Hard end of the window. Required — these are never open-ended.")
    starts_at: datetime | None = Field(default=None, description="Optional future start; defaults to now.")
    reason: str | None = Field(default=None, description="Non-identifying note, e.g. 'cover for absence'.")


class AccessGrantRecord(_Strict):
    grant_id: UUID
    kind: GrantKind
    grantee: UUID
    granted_by: UUID
    app: AppId
    role: Role
    scope: str
    starts_at: datetime
    expires_at: datetime
    reason: str | None = None
    granted_at: datetime
    revoked_at: datetime | None = None
    active: bool = Field(description="True iff not revoked and now within [starts_at, expires_at].")


class ErrorResponse(_Strict):
    error: str
    detail: str | None = None
