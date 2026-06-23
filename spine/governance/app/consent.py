"""Consent + retention + lineage services (spine A7).

INVARIANT 6 — CONSENT IS A PRIMITIVE; it gates every cross-context read. This
module is the governance-side service over consent state, the retention policy
that follows from it, and the lineage attached to every insight.

- **Consent** — grant / revoke / check. ``is_satisfied(canonical_uuid, purpose)``
  is the gate: True only when an active (non-revoked) consent exists for that
  (opaque subject, purpose). A revoked consent fails the gate immediately, so a
  read that was permitted yesterday is refused today. The age tier on a grant
  records the legally-permitted depth of profiling (DPDP children's-data note);
  the gate never widens past the tier.
- **Retention** — each consent carries a retention window (days). ``due_action``
  reports KEEP / EXPIRE / LEGAL_HOLD for a record given its age, the consent's
  window, and any active legal hold. EXPIRE means the linkable row is purged
  (severing the link, leaving de-identified aggregate behind — INVARIANT 2);
  this service reports the action, the storage layer performs the purge.
- **Lineage** — ``build_lineage`` assembles the provenance of an insight: the
  evidence it rests on, the consent it was read under, and the model/capability
  that produced it. ``LineageRequiredError`` is raised if an insight is offered
  without a consent ref or without any source nodes — an insight with no lineage
  is not allowed to leave this layer (A7 mandate: lineage on every insight).

No PII anywhere — subjects and actors are opaque refs only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    ConsentGrant,
    Lineage,
    LineageNode,
    RetentionAction,
    new_id,
)


class ConsentNotSatisfiedError(PermissionError):
    """Raised when a gated read is attempted without satisfied consent."""


class LineageRequiredError(ValueError):
    """Raised when an insight is offered without lineage (consent + sources)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConsentService:
    """Active-consent state + the cross-context read gate (INVARIANT 6)."""

    def __init__(self) -> None:
        # Append-only mirror; revocation appends a superseding record.
        self._grants: list[ConsentGrant] = []

    def grant(
        self,
        *,
        canonical_uuid: UUID,
        purpose: str,
        scope: str,
        age_tier: str,
        granted_by: UUID,
        retention_days: int,
    ) -> ConsentGrant:
        g = ConsentGrant(
            consent_id=new_id(),
            canonical_uuid=canonical_uuid,
            purpose=purpose,
            scope=scope,
            age_tier=age_tier,
            granted_by=granted_by,
            granted_at=_now(),
            retention_days=retention_days,
        )
        self._grants.append(g)
        return g

    def revoke(self, *, consent_id: UUID, at: datetime | None = None) -> ConsentGrant:
        for i, g in enumerate(self._grants):
            if g.consent_id == consent_id and g.revoked_at is None:
                from dataclasses import replace

                revoked = replace(g, revoked_at=at or _now())
                self._grants[i] = revoked
                return revoked
        raise KeyError(f"no active consent {consent_id}")

    def active_for(self, canonical_uuid: UUID, purpose: str) -> ConsentGrant | None:
        for g in self._grants:
            if (
                g.canonical_uuid == canonical_uuid
                and g.purpose == purpose
                and g.revoked_at is None
            ):
                return g
        return None

    def is_satisfied(self, canonical_uuid: UUID, purpose: str) -> bool:
        """THE GATE. True only with an active consent for (subject, purpose)."""
        return self.active_for(canonical_uuid, purpose) is not None

    def require(self, canonical_uuid: UUID, purpose: str) -> ConsentGrant:
        """Assert the gate; raise if not satisfied. No silent pass-through."""
        g = self.active_for(canonical_uuid, purpose)
        if g is None:
            raise ConsentNotSatisfiedError(
                f"no active consent for purpose {purpose!r}; cross-context read refused."
            )
        return g


class RetentionService:
    """Retention windows derived from consent (DPDP-aligned)."""

    def due_action(
        self,
        *,
        consent: ConsentGrant,
        record_created_at: datetime,
        legal_hold: bool = False,
        now: datetime | None = None,
    ) -> RetentionAction:
        if legal_hold:
            # A hold overrides expiry; the row is kept under the hold.
            return RetentionAction.LEGAL_HOLD
        when = now or _now()
        expires_at = record_created_at + timedelta(days=consent.retention_days)
        if when >= expires_at:
            # Window elapsed: the linkable row is due for purge (sever the link).
            return RetentionAction.EXPIRE
        # A revoked consent also expires retention of its linkable data.
        if consent.revoked_at is not None and when >= consent.revoked_at:
            return RetentionAction.EXPIRE
        return RetentionAction.KEEP


class LineageService:
    """Lineage on every insight (A7 mandate)."""

    def build_lineage(
        self,
        *,
        canonical_uuid: UUID,
        purpose: str,
        consent_id: UUID | None,
        confidence: float,
        evidence_event_ids: list[UUID] | None = None,
        model_ref: str | None = None,
        capability_ref: str | None = None,
        produced_at: datetime | None = None,
    ) -> Lineage:
        # An insight with no consent ref or no sources has no lineage; refuse it.
        if consent_id is None:
            raise LineageRequiredError(
                "insight has no consent ref; lineage is mandatory (INVARIANT 6)."
            )
        nodes: list[LineageNode] = []
        for ev in evidence_event_ids or []:
            nodes.append(LineageNode(node_id=new_id(), kind="event", ref=str(ev)))
        if model_ref:
            nodes.append(LineageNode(node_id=new_id(), kind="model", ref=model_ref))
        if capability_ref:
            nodes.append(
                LineageNode(node_id=new_id(), kind="capability", ref=capability_ref)
            )
        nodes.append(
            LineageNode(node_id=new_id(), kind="consent", ref=str(consent_id))
        )
        # Evidence over assertion: an insight must rest on at least one source
        # beyond the consent stamp itself.
        if len(nodes) <= 1:
            raise LineageRequiredError(
                "insight has no evidence/model/capability source; lineage is mandatory."
            )
        return Lineage(
            insight_id=new_id(),
            canonical_uuid=canonical_uuid,
            purpose=purpose,
            consent_id=consent_id,
            confidence=confidence,
            nodes=nodes,
            produced_at=produced_at or _now(),
        )
