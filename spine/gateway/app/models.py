"""Pydantic mirrors of the gateway contract (contracts/src/openapi/gateway.ts)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AppId = Literal["school", "learner", "platform"]
Role = Literal["admin", "teacher", "student", "parent"]
Decision = Literal["allow", "deny"]
Capability = Literal["identity", "event-store"]


class Membership(BaseModel):
    app: AppId
    role: Role
    scope: str
    granted_at: datetime
    revoked_at: datetime | None = None


class VerifiedIdentity(BaseModel):
    """Resolved from the token at the wall. Opaque only — no PII."""

    canonical_uuid: UUID
    app: AppId
    memberships: list[Membership] = Field(default_factory=list)


class PolicyEvaluateRequest(BaseModel):
    capability: str
    operation: str
    resource_scope: str | None = Field(default=None, description="ABAC resource attributes (e.g. institution/grade).")
    purpose: str | None = None


class PolicyDecision(BaseModel):
    decision: Decision
    reasons: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
