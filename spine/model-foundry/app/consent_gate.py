"""The consent + age-tier admissibility gate for TRAINING data (INVARIANT 6).

A learner's behavioural data is usable for model improvement ONLY within the
consent / age tier that permits it. This gate is the single decision point the
foundry consults before any signal is admitted to a dataset. It is:

* DENY-BY-DEFAULT — no record of an active, model-improvement-scoped consent for
  this learner means the signal is inadmissible. Silence is denial.
* AGE-TIER AWARE (DPDP) — minors are far more restricted. A ``child`` is never
  admissible for model improvement; a ``teen`` is admissible ONLY with an
  explicit guardian-granted model-improvement consent; an ``adult`` follows the
  ordinary consent rule.
* REVOCATION-RESPECTING — a revoked consent removes that learner's contributed
  signals entirely (INVARIANT 6 — revocation removes contributed signals). A
  revoked or superseded consent is never admissible.
* TRANSPARENT — every decision carries a plain-language reason and the provenance
  it was decided against, so capture and audit can explain exactly why a signal
  was or was not used.

The gate holds NO PII. It is fed a registry of consent records (themselves PII-
free: opaque ``canonical_uuid`` + ``consent_ref`` + age tier + scope + status),
which a real deployment projects from the immutable ``consent.granted`` /
``consent.revoked`` event stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from uuid import UUID

# The age tiers from the event contract (contracts/src/events/payloads.ts).
AgeTier = Literal["child", "teen", "adult"]

# The scope string a consent must carry for its data to be usable to improve the
# proprietary model. Anything narrower (e.g. plain "learning_behavior" for
# instruction) is NOT a model-improvement grant and is denied here.
MODEL_IMPROVEMENT_SCOPE = "model_improvement"


class ConsentStatus(str, Enum):
    """Lifecycle of a consent record as projected from the event stream."""

    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True)
class ConsentRecord:
    """A PII-free projection of a learner's consent for model improvement.

    Carries only opaque references. ``scope`` is the data scope the consent
    covers; ``status`` reflects the latest consent.granted / consent.revoked for
    this ``consent_ref``.
    """

    consent_ref: UUID
    canonical_uuid: UUID
    age_tier: AgeTier
    scope: str
    status: ConsentStatus = ConsentStatus.ACTIVE
    # For a child/teen, the opaque ref to the guardian who granted it. Required
    # for a teen to be admissible (guardian-granted), informational for adults.
    granted_by: UUID | None = None


class DenyReason(str, Enum):
    """The closed set of reasons a signal can be denied — auditable + stable."""

    NO_CONSENT = "no_active_consent_record_for_learner"
    REVOKED = "consent_revoked_contributions_removed"
    SCOPE_MISMATCH = "consent_scope_does_not_permit_model_improvement"
    MINOR_CHILD_BLOCKED = "child_tier_never_admissible_for_model_improvement"
    TEEN_NO_GUARDIAN = "teen_tier_requires_explicit_guardian_consent"
    CONSENT_REF_MISMATCH = "signal_consent_ref_does_not_match_active_record"


@dataclass(frozen=True)
class AdmissibilityDecision:
    """The gate's verdict for one (learner, consent_ref) pair.

    ``admissible`` is the verdict; ``reason`` is always populated (the allow
    reason or the deny reason) so the decision is self-explaining. ``provenance``
    records exactly what was decided against, for transparent audit.
    """

    admissible: bool
    reason: str
    age_tier: AgeTier | None = None
    deny_reason: DenyReason | None = None
    provenance: dict[str, str] = field(default_factory=dict)


class ConsentGate:
    """Deny-by-default admissibility gate over a registry of consent records.

    Construct from the consent projection (or build it incrementally via
    :meth:`apply_event` from consent.granted / consent.revoked events). The gate
    keeps the LATEST status per ``consent_ref`` so a revocation supersedes a
    prior grant.
    """

    def __init__(self, records: list[ConsentRecord] | None = None) -> None:
        # Keyed by consent_ref so a later revocation overwrites the grant.
        self._by_ref: dict[UUID, ConsentRecord] = {}
        for rec in records or []:
            self._by_ref[rec.consent_ref] = rec

    # -- projection helpers --------------------------------------------------

    def upsert(self, record: ConsentRecord) -> None:
        """Insert or replace a consent record (latest-status-wins per ref)."""
        self._by_ref[record.consent_ref] = record

    def revoke(self, consent_ref: UUID) -> None:
        """Mark a consent revoked. A revoked consent's signals are removed by the
        capture/dataset layers because the gate now denies them."""
        existing = self._by_ref.get(consent_ref)
        if existing is None:
            return
        self._by_ref[consent_ref] = ConsentRecord(
            consent_ref=existing.consent_ref,
            canonical_uuid=existing.canonical_uuid,
            age_tier=existing.age_tier,
            scope=existing.scope,
            status=ConsentStatus.REVOKED,
            granted_by=existing.granted_by,
        )

    def apply_event(self, event: dict) -> None:
        """Fold a consent.granted / consent.revoked envelope into the registry.

        Mirrors the event contract: granted carries scope/purpose/age_tier;
        revoked carries the consent_id. PII-free throughout.
        """
        etype = event.get("type")
        payload = event.get("payload", {})
        if etype == "consent.granted":
            self.upsert(
                ConsentRecord(
                    consent_ref=_as_uuid(payload["consent_id"]),
                    canonical_uuid=_as_uuid(event["canonical_uuid"]),
                    age_tier=payload["age_tier"],
                    scope=payload.get("scope", ""),
                    status=ConsentStatus.ACTIVE,
                    granted_by=_as_uuid(payload["granted_by"]) if payload.get("granted_by") else None,
                )
            )
        elif etype == "consent.revoked":
            self.revoke(_as_uuid(payload["consent_id"]))

    # -- the decision --------------------------------------------------------

    def evaluate(self, *, canonical_uuid: UUID, consent_ref: UUID) -> AdmissibilityDecision:
        """Decide whether a signal stamped (canonical_uuid, consent_ref) may be
        used to improve the model. DENY-BY-DEFAULT.
        """
        record = self._by_ref.get(consent_ref)

        # 1. No record at all -> denied (silence is denial).
        if record is None:
            return AdmissibilityDecision(
                admissible=False,
                reason="No active model-improvement consent on record for this learner.",
                deny_reason=DenyReason.NO_CONSENT,
                provenance={"consent_ref": str(consent_ref), "canonical_uuid": str(canonical_uuid)},
            )

        prov = {
            "consent_ref": str(record.consent_ref),
            "canonical_uuid": str(record.canonical_uuid),
            "age_tier": record.age_tier,
            "scope": record.scope,
            "status": record.status.value,
        }

        # 2. The signal's learner must match the consent record's learner.
        if record.canonical_uuid != canonical_uuid:
            return AdmissibilityDecision(
                admissible=False,
                reason="Signal's learner does not match the consent record's learner.",
                age_tier=record.age_tier,
                deny_reason=DenyReason.CONSENT_REF_MISMATCH,
                provenance=prov,
            )

        # 3. Revoked -> denied; the learner's contributions are removed.
        if record.status is ConsentStatus.REVOKED:
            return AdmissibilityDecision(
                admissible=False,
                reason="Consent was revoked; this learner's contributed signals are removed.",
                age_tier=record.age_tier,
                deny_reason=DenyReason.REVOKED,
                provenance=prov,
            )

        # 4. Scope must explicitly permit model improvement.
        if record.scope != MODEL_IMPROVEMENT_SCOPE:
            return AdmissibilityDecision(
                admissible=False,
                reason="Consent scope does not permit use for model improvement.",
                age_tier=record.age_tier,
                deny_reason=DenyReason.SCOPE_MISMATCH,
                provenance=prov,
            )

        # 5. Age tier (DPDP). Minors are strictly limited.
        if record.age_tier == "child":
            return AdmissibilityDecision(
                admissible=False,
                reason="Child-tier learner data is never admissible for model improvement.",
                age_tier="child",
                deny_reason=DenyReason.MINOR_CHILD_BLOCKED,
                provenance=prov,
            )
        if record.age_tier == "teen" and record.granted_by is None:
            return AdmissibilityDecision(
                admissible=False,
                reason="Teen-tier learner requires an explicit guardian-granted consent.",
                age_tier="teen",
                deny_reason=DenyReason.TEEN_NO_GUARDIAN,
                provenance=prov,
            )

        # All gates cleared.
        return AdmissibilityDecision(
            admissible=True,
            reason="Active, model-improvement-scoped, age-tier-permitted consent on record.",
            age_tier=record.age_tier,
            provenance=prov,
        )

    def is_admissible(self, *, canonical_uuid: UUID, consent_ref: UUID) -> bool:
        """Convenience boolean wrapper over :meth:`evaluate`."""
        return self.evaluate(canonical_uuid=canonical_uuid, consent_ref=consent_ref).admissible


def _as_uuid(value: object) -> UUID:
    """Coerce a contract field (str or UUID) to UUID without leaking PII."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
