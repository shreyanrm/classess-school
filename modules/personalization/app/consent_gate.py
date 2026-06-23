"""The consent + AGE-TIER gate for implicit profiling (INVARIANT 6 + DPDP).

This is the single law of the module: the DEPTH of behavioural profiling that
lights up is bounded by the consent/age tier that legally permits it. We build
only the doors the law provides; we never chase gaps.

Three things are enforced here, denied-by-default:

  1. CONSENT.  No inference proceeds without a live consent grant covering the
     ``profiling`` scope for the ``personalization`` purpose. A revoked or
     expired grant denies. (INVARIANT 6 — consent is a primitive.)

  2. AGE TIER.  Each age tier permits a strictly bounded SET of trait kinds.
     A ``child`` tier infers far less than ``teen``, which infers less than
     ``adult``. Requesting a trait the tier does not permit is DENIED — the door
     does not exist for that learner, regardless of any other consent.

  3. SCOPE.  The consent grant itself may further narrow which traits are
     permitted (a learner/guardian may consent to interest inference but not
     learning-style inference). The effective permitted set is the INTERSECTION
     of the tier ceiling and the grant's named traits.

Everything here is deterministic and offline. It carries no PII — subjects and
grant ids are opaque ``canonical_uuid`` / opaque ids only. The DPDP rules for
children's data must be re-verified before any tier is treated as settled; the
tier ceilings below are deliberately conservative for the child tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Literal

# The age tiers, mirroring the consent contract
# (contracts/src/events/payloads.ts AgeTier). DPDP-shaped: a child is afforded
# the strongest protection and the shallowest profiling.
AgeTier = Literal["child", "teen", "adult"]

# The data scope a personalization consent covers. A grant names the scopes it
# authorizes; the gate matches the requested scope exactly (no implicit widening).
ConsentScope = Literal[
    "profiling",          # implicit behavioural profiling (this module)
    "preferences-hints",  # turning the profile into surface hints
]


class TraitKind(str, Enum):
    """The kinds of trait the engine can infer.

    The age tier draws a CEILING across this set. Ordered loosely from least to
    most sensitive: lightweight surface preferences first, deeper behavioural
    inferences last. A young-child tier sees only the top of this list.
    """

    INTEREST = "interest"                  # topics/subjects the learner gravitates to
    PREFERRED_SUBJECT = "preferred_subject"  # subject(s) most engaged with
    PACE = "pace"                          # how fast the learner likes to move
    GOAL = "goal"                          # what the learner appears to be working toward
    STRENGTH = "strength"                  # where the learner is performing well
    LEARNING_STYLE = "learning_style"      # preferred mode of learning (deepest inference)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Age-tier policy — the legal ceiling on inference depth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierPolicy:
    """What a given age tier legally permits the engine to infer.

    ``permitted`` is the CEILING: the maximal set of trait kinds inferable for a
    learner in this tier. The effective set for a specific learner is this
    ceiling intersected with what their consent grant actually names.

    ``max_confidence`` caps how confident the engine may ever be about an
    inference for this tier — a more protected tier is held to a more provisional
    read, never a hardened label.
    """

    tier: AgeTier
    permitted: frozenset[TraitKind]
    max_confidence: float
    rationale: str

    def permits(self, kind: TraitKind) -> bool:
        return kind in self.permitted


# The tier ceilings. CHILD is deliberately the shallowest: only lightweight,
# non-sensitive surface preferences, and never deep behavioural inference such as
# learning style or inferred goals. TEEN adds pace + goal. ADULT permits the full
# set. These are conservative by design — widen only with verified DPDP guidance.
_CHILD_POLICY = TierPolicy(
    tier="child",
    permitted=frozenset({TraitKind.INTEREST, TraitKind.PREFERRED_SUBJECT}),
    max_confidence=0.6,
    rationale=(
        "A young child is afforded the strongest protection: only lightweight "
        "surface interests and a preferred subject are inferred, never deep "
        "behavioural profiling (no learning-style, goal, pace, or strength "
        "inference)."
    ),
)
_TEEN_POLICY = TierPolicy(
    tier="teen",
    permitted=frozenset(
        {
            TraitKind.INTEREST,
            TraitKind.PREFERRED_SUBJECT,
            TraitKind.PACE,
            TraitKind.GOAL,
            TraitKind.STRENGTH,
        }
    ),
    max_confidence=0.8,
    rationale=(
        "A teen tier adds pace, goal, and strength inference on top of the "
        "child ceiling, but still withholds the deepest learning-style "
        "inference."
    ),
)
_ADULT_POLICY = TierPolicy(
    tier="adult",
    permitted=frozenset(TraitKind),  # the full set
    max_confidence=0.95,
    rationale="An adult tier permits the full set of inferable traits.",
)

_TIER_POLICIES: dict[AgeTier, TierPolicy] = {
    "child": _CHILD_POLICY,
    "teen": _TEEN_POLICY,
    "adult": _ADULT_POLICY,
}


def tier_policy(tier: AgeTier) -> TierPolicy:
    """The legal ceiling policy for an age tier."""
    return _TIER_POLICIES[tier]


# ---------------------------------------------------------------------------
# The consent grant
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PersonalizationConsent:
    """A recorded consent grant authorizing implicit profiling.

    Mirrors the consent contract (ConsentGrantedPayload) reduced to what this
    gate needs. Opaque only — no PII.

    ``traits`` optionally narrows which trait kinds the grant authorizes; ``None``
    means "every trait the tier permits". The effective permitted set is always
    bounded by the age tier ceiling regardless of what the grant names — a grant
    can only ever narrow, never widen, the tier door.
    """

    consent_id: str
    subject: str                              # opaque canonical_uuid of the learner
    age_tier: AgeTier
    scopes: frozenset[ConsentScope]
    purpose: Literal["personalization"] = "personalization"
    traits: frozenset[TraitKind] | None = None
    granted_by: str | None = None             # opaque ref (self, or guardian)
    expires_at: datetime | None = None
    revoked: bool = False

    def is_live(self, *, asof: datetime) -> bool:
        if self.revoked:
            return False
        if self.expires_at is not None and asof >= self.expires_at:
            return False
        return True


def permitted_traits(consent: PersonalizationConsent) -> frozenset[TraitKind]:
    """The effective set of trait kinds this consent legally permits.

    The INTERSECTION of (a) the age-tier ceiling and (b) the traits the grant
    names (or the whole ceiling when the grant names none). This is the set the
    inference engine is allowed to populate; anything outside it is denied.
    """
    ceiling = tier_policy(consent.age_tier).permitted
    if consent.traits is None:
        return ceiling
    return frozenset(ceiling & consent.traits)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class GateResult:
    """The gate's verdict, with a plain-language, explainable reason (principle 2).

    A denial always says WHY in plain language, never leaking PII or which other
    grants exist.
    """

    decision: Decision
    reason: str
    consent_id: str | None = None
    max_confidence: float = 0.0

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class InferenceDenied(PermissionError):
    """Raised when an inference is attempted beyond the consented tier/scope.

    Subclasses ``PermissionError`` so callers treat an over-tier inference as the
    access failure it is. Carries the explainable reason, never PII.
    """

    def __init__(self, result: GateResult) -> None:
        self.result = result
        super().__init__(result.reason)


def evaluate_inference(
    *,
    subject: str,
    trait: TraitKind,
    consents: Iterable[PersonalizationConsent],
    scope: ConsentScope = "profiling",
    asof: datetime | None = None,
) -> GateResult:
    """Evaluate whether a single trait may be inferred for a learner.

    DENIED-BY-DEFAULT. Returns ALLOW only when SOME live consent for this subject
    covers the requested scope AND the requested trait falls inside the effective
    permitted set (tier ceiling ∩ grant traits). Otherwise DENY with a specific,
    PII-free reason.
    """
    asof = asof or _now()

    saw_subject = False
    saw_live = False
    saw_scope = False
    saw_tier_permits = False

    for consent in consents:
        if consent.subject != subject:
            continue
        saw_subject = True
        if not consent.is_live(asof=asof):
            continue
        saw_live = True
        if scope not in consent.scopes:
            continue
        saw_scope = True
        ceiling = tier_policy(consent.age_tier)
        if not ceiling.permits(trait):
            continue
        saw_tier_permits = True
        if trait not in permitted_traits(consent):
            continue
        return GateResult(
            decision=Decision.ALLOW,
            reason=(
                f"A live consent permits '{trait.value}' inference for the "
                f"'{consent.age_tier}' tier under the '{scope}' scope."
            ),
            consent_id=consent.consent_id,
            max_confidence=ceiling.max_confidence,
        )

    if not saw_subject:
        reason = "No personalization consent has been recorded for this learner. Inference denied."
    elif not saw_live:
        reason = "The personalization consent has expired or been revoked. Inference denied."
    elif not saw_scope:
        reason = f"Consent does not cover the '{scope}' scope. Inference denied."
    elif not saw_tier_permits:
        reason = (
            f"The '{trait.value}' inference is beyond what this learner's age "
            f"tier legally permits. Inference denied (over-tier)."
        )
    else:
        reason = (
            f"The learner's consent narrows out the '{trait.value}' trait. "
            "Inference denied."
        )
    return GateResult(decision=Decision.DENY, reason=reason)


def require_inference(
    *,
    subject: str,
    trait: TraitKind,
    consents: Iterable[PersonalizationConsent],
    scope: ConsentScope = "profiling",
    asof: datetime | None = None,
) -> GateResult:
    """Like :func:`evaluate_inference` but RAISES :class:`InferenceDenied` on deny.

    Inference code paths call this so no trait can be populated without passing
    the consent + age-tier gate — an over-tier inference cannot proceed.
    """
    result = evaluate_inference(
        subject=subject, trait=trait, consents=consents, scope=scope, asof=asof
    )
    if not result.allowed:
        raise InferenceDenied(result)
    return result


def effective_max_confidence(
    consents: Iterable[PersonalizationConsent],
    *,
    subject: str,
    asof: datetime | None = None,
) -> float:
    """The confidence cap that applies to this learner's inferences.

    The minimum ceiling across the learner's live grants (the most protective
    wins). Zero when no live grant exists — nothing may be inferred at all.
    """
    asof = asof or _now()
    caps = [
        tier_policy(c.age_tier).max_confidence
        for c in consents
        if c.subject == subject and c.is_live(asof=asof)
    ]
    return min(caps) if caps else 0.0


__all__ = [
    "AgeTier",
    "ConsentScope",
    "TraitKind",
    "TierPolicy",
    "PersonalizationConsent",
    "Decision",
    "GateResult",
    "InferenceDenied",
    "tier_policy",
    "permitted_traits",
    "evaluate_inference",
    "require_inference",
    "effective_max_confidence",
]
