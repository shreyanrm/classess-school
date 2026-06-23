"""The mastery model — six explicit dimensions, multiplicative composite.

    Mastery = Performance x Reliability x Independence x Difficulty x Recency x Consistency

Each dimension is computed in [0,1] from the learner's replayed attempt history
for one topic, then combined as a PRODUCT of dimension^weight (per the contract:
``MASTERY_WEIGHT_MODE = "multiplicative"``). A product, not an average, so a
near-zero on any one dimension — most importantly Independence — caps the whole
reading. That is the design intent: a learner who only performs WITH HELP cannot
read as a master no matter how high their raw success rate.

The output carries BOTH the structured six-dimension breakdown AND a
plain-language band. The raw formula and the composite number are NEVER surfaced
to a learner; ``plain_language`` turns the band into "you can do this
independently" / "you can do this with guidance" / "revision is due".

Pure and deterministic: same evidence in, same reading out.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .evidence import (
    EvidenceItem,
    INDEPENDENT_WEIGHT,
    SUPPORTED_WEIGHT,
    assistance_rank,
    collect_evidence,
    lineage_ids,
)
from .models import (
    EventEnvelope,
    MasteryBand,
    MasteryDimensions,
    MasteryReading,
    MasteryWeights,
    now_utc,
)

# Composite thresholds for the display band. Tuned so that:
#   - any history with zero independent demonstration cannot reach "secure"
#     (Independence near 0 collapses the product),
#   - a steady independent learner lands in "independent".
_BAND_THRESHOLDS = (
    (0.55, "independent"),
    (0.32, "secure"),
    (0.16, "developing"),
    (0.0001, "emerging"),
)

# Independence floor below which the convenience `independent` flag is false
# regardless of composite — the keystone read must be earned independently.
_INDEPENDENT_FLAG_FLOOR = 0.55

# A reading is only meaningful with corroboration; a lone observation yields a
# provisional reading the gap engine will not treat as confirmed.
MIN_OBSERVATIONS_FOR_STABLE_READING = 2


@dataclass(frozen=True)
class MasteryResult:
    """The full structured reading plus lineage. ``reading`` is the contract
    object; ``plain_language`` is the only thing a learner ever sees."""

    topic_id: UUID
    subject: UUID
    reading: MasteryReading
    plain_language: str
    observation_count: int
    independent_observation_count: int
    evidence_event_ids: list[UUID]
    computed_at: datetime

    @property
    def dimensions(self) -> MasteryDimensions:
        return self.reading.dimensions


# ---------------------------------------------------------------------------
# Plain-language mapping (INVARIANT: never show the formula or a raw number)
# ---------------------------------------------------------------------------
_PLAIN_LANGUAGE: dict[MasteryBand, str] = {
    "not-started": "not started yet",
    "emerging": "you are starting to see how this works",
    "developing": "you can do this with guidance",
    "secure": "you can do this reliably, with a little support",
    "independent": "you can do this independently",
}


def plain_language_for(
    band: MasteryBand, *, revision_due: bool, latent_band: MasteryBand | None = None
) -> str:
    """Learner-facing phrasing. Revision-due overrides the band wording so the
    retention message ('revision is due') is never buried.

    The override is judged on LATENT competence (recency-neutralised), not the
    recency-dragged band: strong evidence that has merely gone stale should read
    'revision is due', while a genuinely weak learner never does — staleness
    flags demonstrated mastery for refresh, it does not erase it. ``latent_band``
    defaults to ``band`` so a recent reading is unaffected."""
    judge = latent_band or band
    if revision_due and judge in ("secure", "independent", "developing"):
        return "revision is due"
    return _PLAIN_LANGUAGE[band]


# ---------------------------------------------------------------------------
# The six dimensions. Each returns a value in [0,1].
# ---------------------------------------------------------------------------
def _performance(items: list[EvidenceItem], *, asof: datetime) -> float:
    """Recency-weighted success rate — the starting point."""
    num = sum(it.score * it.weight(asof=asof) for it in items)
    den = sum(it.weight(asof=asof) for it in items)
    return num / den if den > 0 else 0.0


def _reliability(items: list[EvidenceItem], *, asof: datetime) -> float:
    """How DEPENDABLE the performance is across attempts — not one lucky run.

    A single observation is inherently unreliable; reliability ramps up with the
    count of corroborating observations and is pulled down by variance in
    outcomes. This is what stops one good (or bad) score from defining a learner.
    """
    n = len(items)
    if n == 0:
        return 0.0
    # Sample-size confidence: 1 obs -> ~0.5, grows toward 1 with more evidence.
    size_factor = 1.0 - 0.5 ** n
    scores = [it.score for it in items]
    if n == 1:
        spread_factor = 0.5
    else:
        # Lower variance => more reliable. pstdev in [0,0.5] for [0,1] data.
        spread_factor = 1.0 - min(statistics.pstdev(scores) * 2.0, 1.0)
    return max(0.0, min(1.0, size_factor * (0.5 + 0.5 * spread_factor)))


def _independence(items: list[EvidenceItem], *, asof: datetime) -> float:
    """The keystone dimension. SEPARATES independent vs supported attempts.

    Computed as the recency-weighted share of SUCCESSFUL performance that was
    produced independently. An all-supported history -> near 0 even if every
    supported attempt was correct; an all-independent successful history -> ~1.
    A learner climbing the assistance ladder (Learn -> ... -> Independent) sees
    this rise as the support fades.
    """
    indep_credit = 0.0
    total_credit = 0.0
    for it in items:
        w = it.weight(asof=asof)
        contribution = it.score * w
        total_credit += contribution
        if it.independent:
            indep_credit += contribution
        else:
            # Partial credit for climbing the ladder: a near-independent
            # 'Check-my-work' success counts a little toward independence; a
            # fully-scaffolded 'Learn' success counts essentially nothing.
            rank = assistance_rank(it.assistance_level)  # 0..5
            ladder_credit = (rank / 5.0) * 0.5  # cap supported ladder credit at half
            indep_credit += contribution * ladder_credit
    if total_credit <= 0:
        return 0.0
    return max(0.0, min(1.0, indep_credit / total_credit))


def _difficulty(items: list[EvidenceItem], *, asof: datetime) -> float:
    """Difficulty of items SUCCEEDED on — easy wins weigh less than hard ones.

    A learner who only ever succeeds on trivial items should not read as a
    master of the topic; this dimension keeps the bar honest.
    """
    num = 0.0
    den = 0.0
    for it in items:
        w = it.weight(asof=asof)
        # Only successful work earns difficulty credit; map difficulty into a
        # [0.4,1.0] band so a topic of all-easy items doesn't zero the product.
        if it.score > 0:
            num += (0.4 + 0.6 * it.difficulty) * it.score * w
            den += it.score * w
    return num / den if den > 0 else 0.0


def _recency(items: list[EvidenceItem], *, asof: datetime) -> float:
    """How recent the evidence is. Uses the freshest observation's decay so a
    learner who demonstrated yesterday reads high and one whose last evidence is
    months old reads low (links to the retention gap)."""
    if not items:
        return 0.0
    return max(it.recency_weight(asof=asof) for it in items)


def _consistency(items: list[EvidenceItem], *, asof: datetime) -> float:
    """How STABLE performance is over time — erratic reads lower than steady.

    Looks at the trend across the chronological sequence: a steady or improving
    curve reads high; oscillation (right, wrong, right, wrong) reads low.
    """
    n = len(items)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.5
    scores = [it.score for it in items]
    # Mean absolute successive difference — 0 for a flat/monotone line, large
    # for oscillation. Normalize: [0,1] data => MASD in [0,1].
    masd = statistics.mean(abs(scores[i] - scores[i - 1]) for i in range(1, n))
    return max(0.0, min(1.0, 1.0 - masd))


def compute_dimensions(items: list[EvidenceItem], *, asof: datetime) -> MasteryDimensions:
    """The six explicit dimensions for one topic's evidence trail."""
    return MasteryDimensions(
        performance=_performance(items, asof=asof),
        reliability=_reliability(items, asof=asof),
        independence=_independence(items, asof=asof),
        difficulty=_difficulty(items, asof=asof),
        recency=_recency(items, asof=asof),
        consistency=_consistency(items, asof=asof),
    )


def composite(dims: MasteryDimensions, weights: MasteryWeights | None = None) -> float:
    """The collapsed product, for ranking ONLY. PROD_d dimension[d]^weight[d].

    A geometric/multiplicative model: a near-zero dimension caps the result.
    """
    w = weights or MasteryWeights()
    value = 1.0
    for key in MasteryDimensions.model_fields:
        d = getattr(dims, key)
        exp = getattr(w, key)
        # 0 ** anything-positive = 0, which is the intended capping behavior.
        value *= d ** exp
    return max(0.0, min(1.0, value))


def band_for(comp: float, dims: MasteryDimensions, *, n_obs: int) -> MasteryBand:
    """Map composite -> plain band, with guards. No amount of supported success
    can reach 'secure'/'independent' because Independence collapses the product;
    we also refuse 'independent' below the independence floor and refuse any
    confident band on a single observation."""
    if n_obs == 0:
        return "not-started"
    for threshold, band in _BAND_THRESHOLDS:
        if comp >= threshold:
            chosen: MasteryBand = band  # type: ignore[assignment]
            break
    else:
        chosen = "emerging"
    # A single observation never reads above 'developing' — a judgment is never
    # confirmed from one score.
    if n_obs < MIN_OBSERVATIONS_FOR_STABLE_READING and chosen in ("secure", "independent"):
        chosen = "developing"
    # The independent flag/band must be earned independently.
    if chosen == "independent" and dims.independence < _INDEPENDENT_FLAG_FLOOR:
        chosen = "secure"
    return chosen


def compute_mastery(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    topic_id: UUID,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
) -> MasteryResult:
    """Replay the event list into a full mastery reading for one (learner,
    topic). The single public entry point for mastery.

    Deterministic: identical events + asof -> identical reading.
    """
    asof = asof or now_utc()
    items = collect_evidence(events, subject=subject, topic_id=topic_id)
    dims = compute_dimensions(items, asof=asof)
    comp = composite(dims, weights)
    n = len(items)
    band = band_for(comp, dims, n_obs=n)
    is_independent = band == "independent" and dims.independence >= _INDEPENDENT_FLAG_FLOOR
    revision_due = dims.recency < 0.4 and n > 0
    # Judge the revision-due message on latent competence (recency held at full),
    # so strong-but-stale evidence surfaces 'revision is due' rather than reading
    # as a fresh weakness.
    if revision_due:
        latent_dims = dims.model_copy(update={"recency": 1.0})
        latent_band = band_for(composite(latent_dims, weights), latent_dims, n_obs=n)
    else:
        latent_band = band
    reading = MasteryReading(
        dimensions=dims,
        composite=comp,
        band=band,
        independent=is_independent,
    )
    return MasteryResult(
        topic_id=topic_id,
        subject=subject,
        reading=reading,
        plain_language=plain_language_for(band, revision_due=revision_due, latent_band=latent_band),
        observation_count=n,
        independent_observation_count=sum(1 for it in items if it.independent),
        evidence_event_ids=lineage_ids(items),
        computed_at=asof,
    )
