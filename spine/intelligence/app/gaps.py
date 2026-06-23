"""The gap engine — ten gap types, each with its own detection rule.

Collapsing every struggle into one "struggling" signal is exactly what this
taxonomy exists to prevent: each gap type needs a DIFFERENT response, so each
has its own rule reading the evidence trail (and, for prerequisite gaps, the
confirmed prerequisite graph).

CORE invariant: a gap is NEVER confirmed from a single bad score. Every
detection produces a ``GapEvidence`` whose ``confirmed`` flag is true only when
there are at least two corroborating signals (>=2 weak observations, or a weak
attempt plus a weak reassessment). A lone bad score surfaces as an UNCONFIRMED
signal (low confidence) — a prompt to reassess, never a judgment.

Pure and deterministic. The optional second-model cross-check (INVARIANT 7) is a
named, absent provider here; the deterministic rules stand on their own.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .evidence import EvidenceItem, assistance_rank, collect_evidence
from .mastery import MasteryResult, compute_mastery
from .models import (
    EventEnvelope,
    GapEvidence,
    GapType,
    MasteryWeights,
    PrerequisiteGraph,
    now_utc,
)

# A "weak" observation: scored at or below this is treated as a struggle signal.
WEAK_SCORE = 0.5
# Topic-level weakness: a performance dimension at or below this is "weak".
WEAK_PERFORMANCE = 0.55
# Minimum corroborating signals before a gap is CONFIRMED. Never 1.
MIN_SIGNALS_TO_CONFIRM = 2
# "Slow" relative to peers/expectation: this engine has no per-item norm yet, so
# speed is judged against a fixed expectation band (ms). Named so a future norm
# from the feature store can replace it without changing the rule shape.
SLOW_THRESHOLD_MS = 90_000


@dataclass(frozen=True)
class GapResult:
    """A detected gap with full lineage, ready to attach to a mastery update."""

    evidence: GapEvidence
    signal_count: int

    @property
    def gap_type(self) -> GapType:
        return self.evidence.gap_type

    @property
    def confirmed(self) -> bool:
        return self.evidence.confirmed


def _confidence_from_signals(signal_count: int, *, strength: float = 1.0) -> float:
    """More corroborating signals -> higher confidence, asymptotic to 1.
    ``strength`` (0..1) scales for how clear-cut each signal is."""
    if signal_count <= 0:
        return 0.0
    base = 1.0 - 0.5 ** signal_count  # 1->0.5, 2->0.75, 3->0.875
    return max(0.0, min(1.0, base * strength))


def _mk_gap(
    gap_type: GapType,
    *,
    signal_items: list[EvidenceItem],
    rationale: str,
    strength: float = 1.0,
    extra_event_ids: list[UUID] | None = None,
) -> GapResult | None:
    """Build a GapEvidence from corroborating signals. ``confirmed`` is true only
    at/above MIN_SIGNALS_TO_CONFIRM. Returns None when there is no signal at all."""
    ids: list[UUID] = [it.event_id for it in signal_items]
    if extra_event_ids:
        ids.extend(extra_event_ids)
    # De-dupe, preserve order — the lineage.
    seen: dict[UUID, None] = {}
    for i in ids:
        seen.setdefault(i, None)
    ids = list(seen.keys())
    if not ids:
        return None
    n = len(signal_items) + (len(extra_event_ids) if extra_event_ids else 0)
    confirmed = n >= MIN_SIGNALS_TO_CONFIRM
    return GapResult(
        evidence=GapEvidence(
            gap_type=gap_type,
            confidence=_confidence_from_signals(n, strength=strength),
            confirmed=confirmed,
            evidence_event_ids=ids,
            rationale=rationale,
        ),
        signal_count=n,
    )


# ---------------------------------------------------------------------------
# Per-type detection rules. Each takes the topic evidence trail (+ context) and
# returns a GapResult or None.
# ---------------------------------------------------------------------------
def _detect_support_dependency(items: list[EvidenceItem], mastery: MasteryResult) -> GapResult | None:
    """Strong only when supported, weak when independent. The gap the
    Independence dimension exists to surface."""
    supported_success = [it for it in items if not it.independent and it.score >= WEAK_SCORE]
    independent_fail = [it for it in items if it.independent and it.score < WEAK_SCORE]
    # Signal: succeeds with help but performance does not transfer to independent
    # work. Require corroboration: at least two supported successes, and either an
    # independent failure or essentially no independent success at all.
    if len(supported_success) < MIN_SIGNALS_TO_CONFIRM:
        return None
    indep_success = [it for it in items if it.independent and it.score >= WEAK_SCORE]
    if indep_success:
        return None
    signals = supported_success + independent_fail
    return _mk_gap(
        "support-dependency",
        signal_items=signals,
        rationale=(
            "Performs well with assistance but has not yet demonstrated the same "
            "independently. Response: deliberately fade the support."
        ),
        strength=0.9,
    )


def _detect_speed_vs_accuracy(items: list[EvidenceItem]) -> list[GapResult]:
    """Distinguish SPEED (correct but slow) from ACCURACY (method right, slips)."""
    out: list[GapResult] = []

    # SPEED: correct and accurate but consistently slow.
    slow_correct = [
        it for it in items
        if it.correct and it.time_taken_ms is not None and it.time_taken_ms > SLOW_THRESHOLD_MS
    ]
    if len(slow_correct) >= MIN_SIGNALS_TO_CONFIRM:
        g = _mk_gap(
            "speed",
            signal_items=slow_correct,
            rationale=(
                "Work is correct but consistently slower than the timed context "
                "needs. Response: fluency building, not new instruction."
            ),
            strength=0.85,
        )
        if g:
            out.append(g)

    # ACCURACY: mostly-right, error-prone slips — near-misses (partial credit
    # just under full, or correct-then-wrong oscillation on similar items), NOT
    # whole-concept failures.
    near_misses = [it for it in items if 0.5 <= it.score < 1.0]
    if len(near_misses) >= MIN_SIGNALS_TO_CONFIRM:
        g = _mk_gap(
            "accuracy",
            signal_items=near_misses,
            rationale=(
                "Method is right but execution is error-prone (slips, "
                "miscalculation). Response: precision drills and self-checking."
            ),
            strength=0.7,
        )
        if g:
            out.append(g)
    return out


def _detect_conceptual_vs_procedural(items: list[EvidenceItem], mastery: MasteryResult) -> GapResult | None:
    """CONCEPTUAL (idea wrong: fails even with heavy support / scores near zero)
    vs PROCEDURAL (idea ok, steps unreliable: partial scores, fails unsupported
    but progresses when coached)."""
    very_weak = [it for it in items if it.score <= 0.25]
    weak_even_supported = [it for it in very_weak if not it.independent]
    if len(weak_even_supported) >= MIN_SIGNALS_TO_CONFIRM:
        return _mk_gap(
            "conceptual",
            signal_items=weak_even_supported,
            rationale=(
                "Struggles even with support and scores near zero — the "
                "underlying idea is misunderstood, not just the execution. "
                "Response: re-explain and re-anchor the concept."
            ),
            strength=0.85,
        )
    # Procedural: understands enough to get partial credit / be coached through,
    # but cannot reliably execute the steps alone.
    partial_or_coached = [
        it for it in items
        if (0.25 < it.score < WEAK_SCORE) or (not it.independent and it.score < WEAK_SCORE)
    ]
    if len(partial_or_coached) >= MIN_SIGNALS_TO_CONFIRM:
        return _mk_gap(
            "procedural",
            signal_items=partial_or_coached,
            rationale=(
                "The concept is grasped but the method/steps are not reliably "
                "executed. Response: guided practice on the procedure."
            ),
            strength=0.7,
        )
    return None


def _detect_application(items: list[EvidenceItem]) -> GapResult | None:
    """Knows concept/procedure in isolation but cannot transfer to novel/harder
    items: succeeds on easy, fails on the harder (higher-difficulty) ones."""
    easy_success = [it for it in items if it.difficulty <= 0.4 and it.score >= WEAK_SCORE]
    hard_fail = [it for it in items if it.difficulty >= 0.6 and it.score < WEAK_SCORE]
    if easy_success and len(hard_fail) >= MIN_SIGNALS_TO_CONFIRM:
        return _mk_gap(
            "application",
            signal_items=hard_fail,
            rationale=(
                "Handles the idea in isolation but cannot transfer it to novel or "
                "harder problems. Response: varied-context application practice."
            ),
            strength=0.75,
            extra_event_ids=[easy_success[0].event_id],
        )
    return None


def _detect_retention(items: list[EvidenceItem], mastery: MasteryResult, *, asof: datetime) -> GapResult | None:
    """Was demonstrated before but has decayed: earlier independent success, then
    stale or a recent drop. Distinct from never-learned (no prior success)."""
    prior_success = [it for it in items if it.score >= WEAK_SCORE]
    if not prior_success:
        return None
    # Decayed: recency dimension is low AND there was real earlier success.
    if mastery.reading.dimensions.recency < 0.4:
        recent = sorted(items, key=lambda it: it.occurred_at)[-MIN_SIGNALS_TO_CONFIRM:]
        return _mk_gap(
            "retention",
            signal_items=recent,
            rationale=(
                "Was demonstrated before but the evidence has aged and may have "
                "decayed. Response: spaced retrieval and review."
            ),
            strength=0.6,
            extra_event_ids=[prior_success[0].event_id],
        )
    return None


def _detect_confidence(items: list[EvidenceItem]) -> GapResult | None:
    """Capable when supported/unobserved but falters under self-reliance: a
    near-independent rung (Check-my-work / Hint) succeeds, but fully independent
    attempts dip. Distinct from support-dependency (which is heavily-supported
    success with no independent transfer at all)."""
    near_indep_success = [
        it for it in items
        if not it.independent and assistance_rank(it.assistance_level) >= 3 and it.score >= WEAK_SCORE
    ]
    indep_dip = [it for it in items if it.independent and 0.25 <= it.score < WEAK_SCORE]
    if len(near_indep_success) >= 1 and len(indep_dip) >= MIN_SIGNALS_TO_CONFIRM - 1 and indep_dip:
        signals = near_indep_success[:1] + indep_dip
        if len(signals) >= MIN_SIGNALS_TO_CONFIRM:
            return _mk_gap(
                "confidence",
                signal_items=signals,
                rationale=(
                    "Capable with light support but falters under full "
                    "self-reliance. Response: scaffolded autonomy and low-stakes wins."
                ),
                strength=0.65,
            )
    return None


def _detect_prerequisite(
    items: list[EvidenceItem],
    mastery: MasteryResult,
    *,
    events: list[EventEnvelope],
    subject: UUID,
    topic_id: UUID,
    graph: PrerequisiteGraph,
    weights: MasteryWeights | None,
    asof: datetime,
) -> GapResult | None:
    """Weak on this topic AND weak on a CONFIRMED prerequisite topic. Routes back
    to the prerequisite rather than re-teaching the current topic."""
    if mastery.reading.dimensions.performance > WEAK_PERFORMANCE:
        return None  # not weak here -> no prerequisite gap to surface
    prereq_edges = graph.prerequisites_of(topic_id, trusted_only=True)
    for edge in prereq_edges:
        pre = compute_mastery(events, subject=subject, topic_id=edge.from_topic_id, weights=weights, asof=asof)
        if pre.observation_count == 0:
            # No evidence on the prerequisite is itself a (softer) signal it may
            # be missing — but unconfirmed without corroboration on this topic.
            continue
        if pre.reading.dimensions.performance <= WEAK_PERFORMANCE:
            here_weak = [it for it in items if it.score < WEAK_SCORE]
            if len(here_weak) >= 1:
                return _mk_gap(
                    "prerequisite",
                    signal_items=here_weak,
                    rationale=(
                        "Weak on this topic and also weak on its confirmed "
                        f"prerequisite ({edge.kind} edge: {edge.rationale}). "
                        "Response: route back to the prerequisite in the graph."
                    ),
                    strength=0.85,
                    extra_event_ids=pre.evidence_event_ids[:1],
                )
    return None


def _detect_language(items: list[EvidenceItem]) -> GapResult | None:
    """Linguistic barrier rather than the academic concept. This engine has no
    free-text/NLP signal, so language is only PROPOSED (never confirmed) when the
    pattern is consistent with comprehension trouble (slow AND wrong even on easy
    items) — deliberately conservative so it does not masquerade as conceptual.
    A future free-text signal upgrades this without changing the rule shape."""
    slow_wrong_easy = [
        it for it in items
        if it.difficulty <= 0.4 and it.score < WEAK_SCORE
        and it.time_taken_ms is not None and it.time_taken_ms > SLOW_THRESHOLD_MS
    ]
    if len(slow_wrong_easy) >= MIN_SIGNALS_TO_CONFIRM:
        g = _mk_gap(
            "language",
            signal_items=slow_wrong_easy,
            rationale=(
                "Possible comprehension/terminology barrier rather than the "
                "academic concept (slow and wrong even on easy items). Proposed "
                "only — confirm with a free-text or translation signal. Response: "
                "hyperlocalized language support, not re-teaching the concept."
            ),
            strength=0.4,
        )
        if g:
            # Language stays UNCONFIRMED until a richer signal corroborates it.
            return GapResult(
                evidence=g.evidence.model_copy(update={"confirmed": False}),
                signal_count=g.signal_count,
            )
    return None


def detect_gaps(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    topic_id: UUID,
    graph: PrerequisiteGraph | None = None,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
    mastery: MasteryResult | None = None,
) -> list[GapResult]:
    """Run every gap rule over one (learner, topic) evidence trail. Returns all
    detected gaps (confirmed and unconfirmed), each with full lineage.

    A single bad score yields, at most, UNCONFIRMED low-confidence signals — the
    CORE guarantee that a learner judgment is never confirmed from one score.
    """
    asof = asof or now_utc()
    graph = graph or PrerequisiteGraph()
    items = collect_evidence(events, subject=subject, topic_id=topic_id)
    if mastery is None:
        mastery = compute_mastery(events, subject=subject, topic_id=topic_id, weights=weights, asof=asof)

    results: list[GapResult] = []
    if not items:
        return results

    def add(g: GapResult | None) -> None:
        if g is not None:
            results.append(g)

    add(_detect_prerequisite(
        items, mastery, events=events, subject=subject, topic_id=topic_id,
        graph=graph, weights=weights, asof=asof,
    ))
    add(_detect_conceptual_vs_procedural(items, mastery))
    add(_detect_application(items))
    add(_detect_retention(items, mastery, asof=asof))
    add(_detect_support_dependency(items, mastery))
    add(_detect_confidence(items))
    for g in _detect_speed_vs_accuracy(items):
        add(g)
    add(_detect_language(items))

    # Stable ordering: confirmed first, then by confidence desc, then gap type.
    results.sort(key=lambda r: (not r.confirmed, -r.evidence.confidence, r.gap_type))
    return results
