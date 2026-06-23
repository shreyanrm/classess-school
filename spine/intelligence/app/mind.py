"""A MIND FOR EVERY LEARNER — the per-learner LEARNED REPRESENTATION.

The §09 missing artifact: the *cognitive fingerprint*. "Personalisation does not
mean a separate model per student" (§09) — the model is shared; the context is
uniquely theirs. This module derives, from the immutable event history (via the
already-replayed :class:`LearnerProfile`), a compact representation of *how this
specific learner thinks*, that a single shared model call can be conditioned on
so it "behaves like a tutor that has known only them for years".

What the representation captures (each a small, bounded, derived signal):

  - INDEPENDENCE PROFILE: how much of demonstrated competence is independent vs
    scaffolded — the keystone read, surfaced as a tendency not a single topic.
  - GAP-TYPE TENDENCIES: which of the ten gap types this learner recurrently
    shows (confirmed), so the model anticipates the *kind* of stumble.
  - PACE: relative working speed from attempt timing.
  - PREFERRED EXPLANATION STYLE: derived from where the learner gains traction
    (e.g. worked-procedure first vs concept-first), never self-declared PII.
  - RETENTION CURVE PARAMS: the decay half-life and how often retention gaps
    recur — how fast this learner forgets, so review can be timed for them.
  - CONFIDENCE PATTERNS: does competence transfer under self-reliance, or dip.

INVARIANTS honoured here:
  - INVARIANT 1 + 2: NEVER any PII. The representation is keyed by the opaque
    ``canonical_uuid`` and built ONLY from the (already PII-free) profile, which
    is itself a pure projection of opaque events. ``assert_pii_free`` enforces
    it structurally.
  - Derived only from events: the constructor takes a ``LearnerProfile`` (or an
    event list it replays through ``build_profile``), nothing else. Re-running
    over the same events is DETERMINISTIC — the same fingerprint out — which is
    what lets "understanding of every past learner improve as the models
    improve": recompute the representation over the old events with a better
    model and the fingerprint refreshes, no retraining required.
  - GOVERNED read (INVARIANT 5 + 11): the representation is reachable only
    through :func:`open_faucet`, a consent + purpose gated faucet view. A read
    without granted consent for an allowed purpose raises — never leaks.
  - Builds a CONDITIONING PAYLOAD (the shape a model call is conditioned on)
    with a STABLE, versioned shape, carrying source lineage and degrade flags.

This module does NOT train a model. It builds the representation, the governed
accessor, and the conditioning payload builder — the shared model, the uniquely
theirs context.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .evidence import RECENCY_HALF_LIFE, collect_evidence
from .models import GAP_TYPES, EventEnvelope, GapType, MasteryWeights, PrerequisiteGraph
from .profile import LearnerProfile, build_profile

# The conditioning-payload schema version. Bumped only when the payload SHAPE
# changes — the contract a model-conditioning call depends on. Tests pin it.
MIND_SCHEMA_VERSION = "v1"

# Purposes for which conditioning a model on the learned representation is a
# legitimate use. A read for any other purpose is refused by the faucet.
ConditioningPurpose = Literal["instruction", "intervention", "mastery", "practice"]
ALLOWED_CONDITIONING_PURPOSES: tuple[ConditioningPurpose, ...] = (
    "instruction",
    "intervention",
    "mastery",
    "practice",
)

# Plain-language buckets — the representation, like mastery, never surfaces raw
# formula numbers to a human-facing reader; the model gets the bands + a few
# bounded scalars it can reason over.
IndependenceTendency = Literal["mostly-independent", "mixed", "mostly-supported", "not-yet-evidenced"]
PaceTendency = Literal["faster-than-typical", "typical", "more-deliberate", "not-yet-evidenced"]
ExplanationStyle = Literal[
    "concept-first",        # gains traction when the underlying idea is re-anchored
    "worked-procedure",     # gains traction with guided step-by-step procedure
    "varied-application",   # needs transfer to varied / harder contexts
    "spaced-retrieval",     # benefits most from timed review (forgets, then recovers)
    "balanced",             # no single dominant lever yet
]
ConfidencePattern = Literal["transfers", "dips-under-self-reliance", "not-yet-evidenced"]

# Typical attempt time used to judge pace (ms). Named, not a per-item norm yet;
# a feature-store norm replaces it later without changing the representation
# shape — mirrors the SLOW_THRESHOLD_MS pattern in gaps.py.
TYPICAL_ATTEMPT_MS = 30_000


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# The learned representation — the cognitive fingerprint.
# ---------------------------------------------------------------------------
class IndependenceProfile(_Model):
    """How much demonstrated competence is independent vs scaffolded."""

    independence_index: float = Field(ge=0, le=1, description="Recency-weighted share of competence shown independently.")
    tendency: IndependenceTendency
    topics_independent: int = Field(ge=0)
    topics_supported_only: int = Field(ge=0)


class RetentionParams(_Model):
    """How fast this learner forgets — for timing review FOR them."""

    half_life_days: float = Field(gt=0, description="Effective retention half-life (engine default, adjusted by observed recurrence).")
    retention_gap_recurrence: float = Field(ge=0, le=1, description="Share of topics showing a confirmed retention gap.")
    review_due_topics: int = Field(ge=0, description="Topics whose evidence has gone stale (revision due).")


class CognitiveFingerprint(_Model):
    """The compact, PII-FREE per-learner LEARNED REPRESENTATION.

    Keyed by the opaque ``canonical_uuid`` ONLY. Every field is a small derived
    signal — no raw events, no free text from the learner, no identity. This is
    the artifact a shared model call is conditioned on."""

    canonical_uuid: UUID = Field(description="Opaque identity ref (INVARIANT 1, 2). The ONLY id present.")
    schema_version: Literal["v1"] = MIND_SCHEMA_VERSION

    independence: IndependenceProfile
    pace: PaceTendency
    preferred_explanation_style: ExplanationStyle
    retention: RetentionParams
    confidence_pattern: ConfidencePattern

    # Gap-type tendencies: gap_type -> recurrence in [0,1] across the learner's
    # topics (confirmed gaps only). Only types that actually recur appear.
    gap_tendencies: dict[GapType, float] = Field(default_factory=dict)

    # Bounded counters for context, never identifying.
    topic_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)

    # Provenance + governance metadata.
    computed_at: datetime
    # Source event-id lineage (opaque uuids) — every conclusion is traceable.
    evidence_event_ids: list[UUID] = Field(default_factory=list)
    # Names (never values) of env vars whose absence kept the engine degraded.
    degraded_reasons: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Derivation — pure functions over the (PII-free) profile.
# ---------------------------------------------------------------------------
def _independence_profile(profile: LearnerProfile) -> IndependenceProfile:
    indices: list[float] = []
    indep_topics = 0
    supported_only = 0
    for proj in profile.topics.values():
        idx = proj.mastery.reading.dimensions.independence
        indices.append(idx)
        if proj.mastery.reading.independent:
            indep_topics += 1
        elif proj.mastery.independent_observation_count == 0 and proj.mastery.observation_count > 0:
            supported_only += 1
    if not indices:
        return IndependenceProfile(
            independence_index=0.0, tendency="not-yet-evidenced",
            topics_independent=0, topics_supported_only=0,
        )
    mean_idx = statistics.mean(indices)
    if mean_idx >= 0.6:
        tendency: IndependenceTendency = "mostly-independent"
    elif mean_idx >= 0.35:
        tendency = "mixed"
    else:
        tendency = "mostly-supported"
    return IndependenceProfile(
        independence_index=mean_idx,
        tendency=tendency,
        topics_independent=indep_topics,
        topics_supported_only=supported_only,
    )


def _gap_tendencies(profile: LearnerProfile) -> dict[GapType, float]:
    """Recurrence of each CONFIRMED gap type across the learner's topics.

    A tendency is a *pattern*, so only confirmed gaps count, and the value is the
    share of touched topics on which that type recurs — robust to a single topic.
    Ordered by the canonical GAP_TYPES order for a stable payload."""
    n_topics = len(profile.topics)
    if n_topics == 0:
        return {}
    counts: dict[GapType, int] = {}
    for proj in profile.topics.values():
        seen_here: set[GapType] = set()
        for g in proj.confirmed_gaps:
            if g.gap_type not in seen_here:
                counts[g.gap_type] = counts.get(g.gap_type, 0) + 1
                seen_here.add(g.gap_type)
    out: dict[GapType, float] = {}
    for gt in GAP_TYPES:
        if gt in counts:
            out[gt] = counts[gt] / n_topics
    return out


def _pace(profile: LearnerProfile, events: list[EventEnvelope] | None) -> PaceTendency:
    """Relative working speed from attempt timing across topics.

    Pace is an event-level signal (attempt timing), so it is derived by replaying
    the SAME events the profile was built from, scoped to the profile's subject
    and touched topics — deterministic, PII-free, and consistent with the profile.
    Without the event list (a profile-only derivation), pace is not-yet-evidenced.
    """
    if not events:
        return "not-yet-evidenced"
    times: list[int] = []
    for topic_id in profile.topics:
        for item in collect_evidence(events, subject=profile.subject, topic_id=topic_id):
            if item.time_taken_ms is not None and item.source == "attempt":
                times.append(item.time_taken_ms)
    if not times:
        return "not-yet-evidenced"
    median = statistics.median(times)
    if median <= TYPICAL_ATTEMPT_MS * 0.7:
        return "faster-than-typical"
    if median >= TYPICAL_ATTEMPT_MS * 1.5:
        return "more-deliberate"
    return "typical"


def _confidence_pattern(profile: LearnerProfile) -> ConfidencePattern:
    """Does competence transfer under self-reliance, or dip? Reads the confidence
    and support-dependency gap tendencies plus the independence index."""
    has_confidence_gap = any(
        any(g.gap_type in ("confidence", "support-dependency") for g in proj.confirmed_gaps)
        for proj in profile.topics.values()
    )
    indep = _independence_profile(profile)
    if indep.tendency == "not-yet-evidenced":
        return "not-yet-evidenced"
    if has_confidence_gap or indep.tendency == "mostly-supported":
        return "dips-under-self-reliance"
    return "transfers"


def _preferred_explanation_style(profile: LearnerProfile) -> ExplanationStyle:
    """Which lever this learner most needs — derived from the dominant recurring
    gap type, NOT a self-declared preference (which would be unverified PII).

    A learner whose recurring stumble is conceptual gains most from re-anchoring
    the idea (concept-first); procedural -> worked steps; application -> varied
    contexts; retention -> spaced retrieval. With no dominant signal: balanced.
    """
    tendencies = _gap_tendencies(profile)
    if not tendencies:
        return "balanced"
    style_for: dict[GapType, ExplanationStyle] = {
        "conceptual": "concept-first",
        "prerequisite": "concept-first",
        "procedural": "worked-procedure",
        "accuracy": "worked-procedure",
        "speed": "worked-procedure",
        "application": "varied-application",
        "retention": "spaced-retrieval",
    }
    # Pick the strongest-recurring mappable gap type; ties break by GAP_TYPES order.
    best: tuple[float, int, ExplanationStyle] | None = None
    for idx, gt in enumerate(GAP_TYPES):
        if gt in tendencies and gt in style_for:
            cand = (tendencies[gt], -idx, style_for[gt])
            if best is None or cand > best:
                best = cand
    return best[2] if best is not None else "balanced"


def _retention_params(profile: LearnerProfile) -> RetentionParams:
    half_life = RECENCY_HALF_LIFE.total_seconds() / 86400.0
    n_topics = len(profile.topics)
    retention_topics = sum(
        1 for proj in profile.topics.values()
        if any(g.gap_type == "retention" for g in proj.confirmed_gaps)
    )
    review_due = sum(
        1 for proj in profile.topics.values()
        if proj.mastery.plain_language == "revision is due"
    )
    recurrence = (retention_topics / n_topics) if n_topics else 0.0
    # A learner who recurrently shows retention gaps effectively forgets faster:
    # shorten the working half-life proportionally (bounded, deterministic). This
    # is the per-learner adjustment a model uses to time review FOR them.
    adjusted = half_life * (1.0 - 0.5 * recurrence)
    return RetentionParams(
        half_life_days=adjusted,
        retention_gap_recurrence=recurrence,
        review_due_topics=review_due,
    )


def _all_lineage(profile: LearnerProfile) -> list[UUID]:
    seen: dict[UUID, None] = {}
    for proj in profile.topics.values():
        for eid in proj.mastery.evidence_event_ids:
            seen.setdefault(eid, None)
    return list(seen.keys())


def derive_fingerprint(
    profile: LearnerProfile,
    *,
    events: list[EventEnvelope] | None = None,
) -> CognitiveFingerprint:
    """Derive the cognitive fingerprint from a (PII-free) learner profile.

    Pure + deterministic: same profile -> same fingerprint. The profile is itself
    a deterministic replay of the events, so two derivations over the same event
    history are identical (the replay guarantee §10).

    ``events`` (optional) is the same immutable list the profile was built from;
    it is used ONLY to derive the attempt-timing pace signal, scoped to the
    profile's subject. Omit it for a profile-only derivation (pace then reads
    'not-yet-evidenced')."""
    obs = sum(proj.mastery.observation_count for proj in profile.topics.values())
    return CognitiveFingerprint(
        canonical_uuid=profile.subject,
        independence=_independence_profile(profile),
        pace=_pace(profile, events),
        preferred_explanation_style=_preferred_explanation_style(profile),
        retention=_retention_params(profile),
        confidence_pattern=_confidence_pattern(profile),
        gap_tendencies=_gap_tendencies(profile),
        topic_count=len(profile.topics),
        observation_count=obs,
        computed_at=profile.computed_at,
        evidence_event_ids=_all_lineage(profile),
        degraded_reasons=list(profile.degraded_reasons),
    )


def build_fingerprint(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    graph: PrerequisiteGraph | None = None,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
    degraded_reasons: list[str] | None = None,
) -> CognitiveFingerprint:
    """Build the fingerprint straight from the event list (replay -> profile ->
    fingerprint). The recomputable/replayable entry point: re-run over the same
    events (e.g. with a better model later) and the fingerprint refreshes."""
    profile = build_profile(
        events, subject=subject, graph=graph, weights=weights, asof=asof,
        degraded_reasons=degraded_reasons,
    )
    return derive_fingerprint(profile, events=events)


# ---------------------------------------------------------------------------
# PII guard — structural enforcement of INVARIANT 1 + 2.
# ---------------------------------------------------------------------------
def assert_pii_free(fp: CognitiveFingerprint) -> None:
    """Raise if the fingerprint carries anything but opaque uuids + bounded
    derived signals. The representation must never accrete PII as it grows."""
    dumped = fp.model_dump(mode="python")
    # The only uuids permitted: the canonical_uuid and the evidence lineage ids.
    allowed_uuid_locations = {"canonical_uuid", "evidence_event_ids"}

    def _walk(node, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")
        elif isinstance(node, UUID):
            top = path.split(".")[1] if "." in path else path
            if top.split("[")[0] not in allowed_uuid_locations:
                raise ValueError(f"PII guard: unexpected uuid at {path}")
        elif isinstance(node, str):
            # Strings are bounded enum bands / version / env-var NAMES only. A
            # band/style/version never contains a digit-run that could be an
            # identifier or contact detail. degraded_reasons are env-var NAMES by
            # design (e.g. clss.intelligence.dev.*) and are exempt.
            top = path.split(".")[1] if "." in path else path
            base = top.split("[")[0]
            digit_exempt = {"degraded_reasons", "schema_version"}
            if base not in digit_exempt and any(ch.isdigit() for ch in node):
                raise ValueError(f"PII guard: unexpected free-form/digit string at {path}: {node!r}")

    _walk(dumped, "fp")


# ---------------------------------------------------------------------------
# The CONDITIONING PAYLOAD — the stable shape a shared model call is conditioned
# on. This is what makes "the model is shared; the context is uniquely theirs".
# ---------------------------------------------------------------------------
class ConditioningPayload(_Model):
    """The stable, versioned shape passed alongside a shared-model call.

    A model is NOT trained here. This payload is the *context* — the learner's
    cognitive fingerprint rendered into a compact, model-ready block plus
    plain-language tutor guidance. The shape is pinned by ``schema_version`` and
    its tests so a model-conditioning caller can depend on it."""

    schema_version: Literal["v1"] = MIND_SCHEMA_VERSION
    canonical_uuid: UUID
    purpose: ConditioningPurpose

    # The compact derived signals, model-ready.
    independence_tendency: IndependenceTendency
    independence_index: float = Field(ge=0, le=1)
    pace: PaceTendency
    preferred_explanation_style: ExplanationStyle
    confidence_pattern: ConfidencePattern
    retention_half_life_days: float = Field(gt=0)
    review_due_topic_count: int = Field(ge=0)
    # Ordered, recurring gap types only (canonical order) — the kinds of stumble
    # the model should anticipate. Plain enum tokens, never raw scores.
    recurring_gap_types: list[GapType] = Field(default_factory=list)

    # Plain-language tutor directives synthesised from the fingerprint — the
    # "tutor that has known only them for years" voice, ready to prepend.
    tutor_directives: list[str] = Field(default_factory=list)

    # Provenance: how much evidence stands behind this, and whether degraded.
    topic_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    evidence_event_ids: list[UUID] = Field(default_factory=list)
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)


_STYLE_DIRECTIVE: dict[ExplanationStyle, str] = {
    "concept-first": "Re-anchor the underlying idea before any procedure; this learner gains most from why before how.",
    "worked-procedure": "Lead with a clear worked example and explicit steps; method clarity matters more than novelty here.",
    "varied-application": "Push transfer to varied and harder contexts; isolated practice is already secure.",
    "spaced-retrieval": "Favour short spaced-retrieval review; this learner recovers fast but forgets fast.",
    "balanced": "No single dominant lever yet; keep explanation style adaptive.",
}
_INDEP_DIRECTIVE: dict[IndependenceTendency, str] = {
    "mostly-independent": "Default to minimal scaffolding; offer help only on request.",
    "mixed": "Offer scaffolding but fade it deliberately as the learner succeeds.",
    "mostly-supported": "Scaffold actively, then fade support toward independent demonstration.",
    "not-yet-evidenced": "Not enough evidence yet; start neutral and observe.",
}
_CONFIDENCE_DIRECTIVE: dict[ConfidencePattern, str] = {
    "transfers": "Competence transfers under self-reliance; low-stakes independent practice is safe.",
    "dips-under-self-reliance": "Competence dips under full self-reliance; build confidence with low-stakes wins.",
    "not-yet-evidenced": "",
}
_PACE_DIRECTIVE: dict[PaceTendency, str] = {
    "faster-than-typical": "Works quickly; guard against rushing slips rather than pace.",
    "typical": "",
    "more-deliberate": "Works deliberately; allow time and avoid penalising pace.",
    "not-yet-evidenced": "",
}


def build_conditioning_payload(
    fp: CognitiveFingerprint,
    *,
    purpose: ConditioningPurpose,
) -> ConditioningPayload:
    """Render a fingerprint into the stable conditioning payload for a model
    call. Deterministic; the directive list order is fixed (style, independence,
    confidence, pace, retention) so the payload is reproducible and diff-stable."""
    directives: list[str] = []
    directives.append(_STYLE_DIRECTIVE[fp.preferred_explanation_style])
    directives.append(_INDEP_DIRECTIVE[fp.independence.tendency])
    if _CONFIDENCE_DIRECTIVE[fp.confidence_pattern]:
        directives.append(_CONFIDENCE_DIRECTIVE[fp.confidence_pattern])
    if _PACE_DIRECTIVE[fp.pace]:
        directives.append(_PACE_DIRECTIVE[fp.pace])
    if fp.retention.review_due_topics > 0:
        directives.append(
            "Some previously-demonstrated topics are due for review; weave in spaced retrieval."
        )

    return ConditioningPayload(
        canonical_uuid=fp.canonical_uuid,
        purpose=purpose,
        independence_tendency=fp.independence.tendency,
        independence_index=fp.independence.independence_index,
        pace=fp.pace,
        preferred_explanation_style=fp.preferred_explanation_style,
        confidence_pattern=fp.confidence_pattern,
        retention_half_life_days=fp.retention.half_life_days,
        review_due_topic_count=fp.retention.review_due_topics,
        recurring_gap_types=list(fp.gap_tendencies.keys()),
        tutor_directives=directives,
        topic_count=fp.topic_count,
        observation_count=fp.observation_count,
        evidence_event_ids=list(fp.evidence_event_ids),
        degraded=bool(fp.degraded_reasons),
        degraded_reasons=list(fp.degraded_reasons),
    )


# ---------------------------------------------------------------------------
# The GOVERNED accessor — a consent + purpose gated faucet view (INVARIANT 5,
# 11). The representation is NEVER reachable except through this gate.
# ---------------------------------------------------------------------------
class ConsentDenied(Exception):
    """Raised when a governed read is attempted without granted consent."""


class PurposeNotPermitted(Exception):
    """Raised when a governed read is attempted for a purpose outside the
    consented, allowed conditioning purposes."""


@dataclass(frozen=True)
class ConsentGrant:
    """A consent grant the faucet checks. Carries the opaque consent ref and the
    purposes the learner (or their guardian, per the age tier) consented to for
    conditioning a model on their representation. No PII — opaque refs + enums."""

    subject: UUID
    consent_ref: UUID
    granted: bool
    purposes: frozenset[ConditioningPurpose] = field(default_factory=frozenset)

    def permits(self, *, subject: UUID, purpose: ConditioningPurpose) -> bool:
        return (
            self.granted
            and self.subject == subject
            and purpose in self.purposes
        )


def open_faucet(
    fp: CognitiveFingerprint,
    *,
    purpose: ConditioningPurpose,
    consent: ConsentGrant,
) -> ConditioningPayload:
    """The governed read — a faucet view, not bulk access (§10).

    A model-conditioning caller reads the representation ONLY through here. The
    gate enforces, in order:
      1. ``purpose`` is an allowed conditioning purpose at all,
      2. consent is granted, for THIS subject, for THIS purpose.
    Any failure raises and NOTHING leaks. On success it returns the scoped
    conditioning payload — never the raw fingerprint, never the underlying
    events (no bulk read of the store, per the firehose-up / faucet-down rule).
    """
    if purpose not in ALLOWED_CONDITIONING_PURPOSES:
        raise PurposeNotPermitted(f"purpose {purpose!r} is not an allowed conditioning purpose")
    if not consent.granted:
        raise ConsentDenied("consent is not granted for this subject")
    if consent.subject != fp.canonical_uuid:
        raise ConsentDenied("consent grant does not match the representation's subject")
    if not consent.permits(subject=fp.canonical_uuid, purpose=purpose):
        raise PurposeNotPermitted(
            f"consent does not cover purpose {purpose!r} for this subject"
        )
    return build_conditioning_payload(fp, purpose=purpose)
