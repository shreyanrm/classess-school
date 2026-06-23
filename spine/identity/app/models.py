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
Role = Literal["admin", "teacher", "student", "parent"]
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


class ErrorResponse(_Strict):
    error: str
    detail: str | None = None
