"""The personalization profile projection — built by replaying signals.

This is the read view: a PII-free personalization profile keyed by the opaque
``canonical_uuid``, produced by REPLAYING the learner's behavioural signals
through the consent + age-tier-gated inference engine. It is IDEMPOTENT — the
same signals and the same consent always yield the same profile — and it is
PROVISIONAL throughout: it never holds a hardened label, only current best reads
re-derivable from fresh signal.

REVOCATION is the load-bearing behaviour here. Revoking consent (or narrowing
it) does not "delete a record" — it changes which doors the law provides, and a
replay through the new consent simply does not infer the now-unpermitted traits.
:func:`project_profile` with a revoked grant clears the inferred traits that the
revocation no longer permits, leaving only what consent still allows. The
profile is the function of (signals, consent); change either and replay.

This module does not author mastery and holds no PII.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .consent_gate import PersonalizationConsent, TraitKind
from .infer import (
    InferenceInput,
    InferredProfile,
    InferredTrait,
    Signal,
    OnboardingChoice,
    infer_profile,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PersonalizationProfile:
    """The projected personalization profile for one learner.

    Keyed by the opaque ``subject`` (canonical_uuid). Holds the gated, evidenced,
    provisional traits and the set of trait kinds the consent/age-tier gate
    refused (for transparency). Carries the signal-set fingerprint so a caller can
    tell whether a replay would change anything (idempotency check).
    """

    subject: str
    traits: tuple[InferredTrait, ...]
    projected_at: datetime
    denied_traits: tuple[tuple[str, str], ...] = ()
    source_signal_ids: tuple[str, ...] = ()

    def trait(self, kind: TraitKind) -> InferredTrait | None:
        for t in self.traits:
            if t.kind == kind:
                return t
        return None

    @property
    def trait_kinds(self) -> frozenset[TraitKind]:
        return frozenset(t.kind for t in self.traits)

    def is_empty(self) -> bool:
        return not self.traits


def _signal_ids(inp: InferenceInput) -> tuple[str, ...]:
    return tuple(sorted(s.signal_id for s in inp.all_signals()))


def project_profile(
    inp: InferenceInput,
    *,
    consents: Iterable[PersonalizationConsent],
    asof: datetime | None = None,
) -> PersonalizationProfile:
    """Project the personalization profile by replaying signals through the gate.

    IDEMPOTENT: identical (signals, consent, asof) inputs always produce an
    identical profile. The projection is a pure function of its inputs — it holds
    no hidden state and mutates nothing.

    REVOCABLE: pass a revoked or narrowed consent and the replay simply does not
    infer the no-longer-permitted traits; they are absent from the result (and
    listed under ``denied_traits`` for transparency). Revoking ALL consent yields
    an empty profile — nothing inferred remains.
    """
    asof = asof or _now()
    inferred: InferredProfile = infer_profile(inp, consents=consents, asof=asof)
    return PersonalizationProfile(
        subject=inferred.subject,
        traits=inferred.traits,
        projected_at=inferred.inferred_at,
        denied_traits=inferred.denied_traits,
        source_signal_ids=_signal_ids(inp),
    )


def replay(
    subject: str,
    signals: Iterable[Signal] = (),
    onboarding_choices: Iterable[OnboardingChoice] = (),
    *,
    consents: Iterable[PersonalizationConsent],
    asof: datetime | None = None,
) -> PersonalizationProfile:
    """Convenience: build the input and project in one call.

    Replaying with the SAME signals after fresh signal arrives re-derives the
    profile from scratch — the profile updates on fresh signal, never accreting a
    permanent label.
    """
    inp = InferenceInput(
        subject=subject,
        signals=tuple(signals),
        onboarding_choices=tuple(onboarding_choices),
    )
    return project_profile(inp, consents=consents, asof=asof)


def clear_on_revocation(
    profile: PersonalizationProfile,
    inp: InferenceInput,
    *,
    consents: Iterable[PersonalizationConsent],
    asof: datetime | None = None,
) -> PersonalizationProfile:
    """Re-project after a consent change, clearing now-unpermitted inferred traits.

    A thin, explicit alias around :func:`project_profile` for the revocation flow,
    so call sites read as intent: "consent changed — re-derive what remains
    permitted." Any trait the new consent no longer permits is gone from the
    result; what consent still allows is retained (re-inferred from the same
    signals). ``profile`` is accepted for symmetry/auditing and is not mutated
    (the projection is pure).
    """
    return project_profile(inp, consents=consents, asof=asof)


__all__ = [
    "PersonalizationProfile",
    "project_profile",
    "replay",
    "clear_on_revocation",
]
