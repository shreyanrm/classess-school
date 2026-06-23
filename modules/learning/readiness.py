"""Exam-readiness forecasting from mastery + coverage (B7).

Readiness answers: "for this exam (a set of ontology topics, optionally
weighted), how ready is the learner, and where is the risk?" It is a FORECAST,
composed transparently from two things the platform already computes:

  - MASTERY per topic — the CORE engine's six-dimension reading (consumed, never
    re-derived here). Crucially, readiness leans on INDEPENDENCE: a topic the
    learner can only do WITH help is NOT exam-ready, because an exam is an
    unaided demonstration. Supported-only mastery is discounted sharply.
  - COVERAGE — has the learner actually produced evidence on each examined
    topic? A topic with no evidence is an unknown, not a pass; unknowns drag
    readiness down and surface as the first thing to address.

Two further honest discounts:
  - RETENTION: a topic that was secure but has decayed (revision due) is not
    counted as currently exam-ready — it needs review first.
  - CONFIRMED GAPS: a confirmed gap on an examined topic is a concrete risk and
    lowers readiness for that topic.

The output is a forecast with a plain-language verdict (never a raw percentage
shown as the headline to a learner — CONFIDENTIALITY SCRUB: plain language) plus
a transparent, evidence-linked breakdown of WHICH topics carry the risk, so the
next study action is obvious. A forecast is never a single opaque number; it is
explained.

Consumes the intelligence engine via :mod:`learning._engine`; degrades to a
deterministic fallback over plain per-topic states when the engine is absent.
Pure and import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

# Band -> a base readiness contribution in [0,1]. Independent is the only band
# that is fully exam-ready (an exam is unaided); secure is strong but carries a
# small support-dependency discount; developing/emerging are not yet ready.
_BAND_READINESS: dict[str, float] = {
    "not-started": 0.0,
    "emerging": 0.15,
    "developing": 0.4,
    "secure": 0.75,
    "independent": 1.0,
}

# Independence floor below which a topic's readiness is capped hard — you cannot
# be exam-ready on something you can only do with help.
_INDEPENDENCE_CAP_FLOOR = 0.45
# The cap applied when independence is below the floor.
_LOW_INDEPENDENCE_CAP = 0.5
# Penalty multipliers for honest discounts.
_REVISION_DUE_FACTOR = 0.6     # decayed -> needs review first
_CONFIRMED_GAP_FACTOR = 0.55   # a confirmed gap is a concrete risk
# Readiness thresholds for the plain-language verdict.
_READY_THRESHOLD = 0.8
_NEARLY_THRESHOLD = 0.6
_BUILDING_THRESHOLD = 0.35


@dataclass(frozen=True)
class TopicReadiness:
    """One examined topic's readiness contribution, with its risk and reason."""

    topic_id: str
    weight: float                 # this topic's share of the exam (normalized)
    has_evidence: bool
    band: str
    independence: float
    revision_due: bool
    confirmed_gap_types: tuple[str, ...]
    readiness: float              # this topic's readiness in [0,1]
    risk: str                     # "ready" | "review" | "gap" | "weak" | "unknown"
    reason: str                   # plain-language why


@dataclass(frozen=True)
class ReadinessForecast:
    """The composed exam-readiness forecast. Transparent, evidence-linked."""

    overall: float                          # weighted readiness in [0,1]
    coverage: float                         # share of examined topics with evidence
    verdict: str                            # plain-language headline (never a %)
    topics: tuple[TopicReadiness, ...]
    degraded: bool

    @property
    def at_risk(self) -> list[TopicReadiness]:
        """Examined topics that are not yet ready, most urgent first."""
        risky = [t for t in self.topics if t.risk != "ready"]
        risky.sort(key=lambda t: (t.readiness, -t.weight, t.topic_id))
        return risky

    @property
    def next_actions(self) -> list[str]:
        """The plain-language next study steps, derived from the riskiest topics
        first. No names, no numbers — clean prose."""
        return [t.reason for t in self.at_risk[:5]]


@dataclass(frozen=True)
class ExamTopic:
    """One topic on the exam blueprint, with its weight (share of the exam)."""

    topic_id: str
    weight: float = 1.0


@dataclass(frozen=True)
class TopicMasteryView:
    """The minimal per-topic mastery view readiness needs. BOTH the engine path
    and the fallback produce this, so the forecast logic is identical."""

    topic_id: str
    has_evidence: bool
    band: str
    independence: float
    revision_due: bool
    confirmed_gap_types: tuple[str, ...] = ()


def _topic_readiness(view: TopicMasteryView, *, weight: float) -> TopicReadiness:
    if not view.has_evidence:
        return TopicReadiness(
            topic_id=view.topic_id, weight=weight, has_evidence=False,
            band=view.band, independence=view.independence, revision_due=False,
            confirmed_gap_types=(), readiness=0.0, risk="unknown",
            reason="No evidence on this topic yet — practise it to know where you stand.",
        )

    score = _BAND_READINESS.get(view.band, 0.0)

    # Independence cap: an exam is unaided. Low independence caps readiness.
    if view.independence < _INDEPENDENCE_CAP_FLOOR:
        score = min(score, _LOW_INDEPENDENCE_CAP)

    risk = "ready"
    reason = "You can do this independently — exam-ready."

    if view.revision_due:
        score *= _REVISION_DUE_FACTOR
        risk = "review"
        reason = "You knew this, but revision is due — review it before the exam."

    if view.confirmed_gap_types:
        score *= _CONFIRMED_GAP_FACTOR
        risk = "gap"
        reason = (
            "There is a confirmed gap here to close before the exam: "
            + ", ".join(view.confirmed_gap_types) + "."
        )

    if score < _BUILDING_THRESHOLD and risk == "ready":
        risk = "weak"
        reason = "You are still building this — keep practising before the exam."

    if view.independence < _INDEPENDENCE_CAP_FLOOR and risk in ("ready", "weak"):
        risk = "weak"
        reason = (
            "You can do this with help, but an exam is on your own — practise it "
            "independently before the exam."
        )

    return TopicReadiness(
        topic_id=view.topic_id, weight=weight, has_evidence=True,
        band=view.band, independence=view.independence,
        revision_due=view.revision_due,
        confirmed_gap_types=tuple(view.confirmed_gap_types),
        readiness=max(0.0, min(1.0, score)), risk=risk, reason=reason,
    )


def _verdict(overall: float, coverage: float) -> str:
    """Plain-language headline — never a raw percentage as the headline."""
    if coverage < 0.5:
        return "too early to forecast — there is not enough practice yet to tell"
    if overall >= _READY_THRESHOLD:
        return "you are on track for this exam"
    if overall >= _NEARLY_THRESHOLD:
        return "you are nearly there — a few topics need attention"
    if overall >= _BUILDING_THRESHOLD:
        return "you are building toward this — several topics still need work"
    return "this needs sustained practice before the exam"


def forecast(views: Iterable[TopicMasteryView], blueprint: Iterable[ExamTopic], *, degraded: bool = False) -> ReadinessForecast:
    """Compose the exam-readiness forecast from per-topic mastery views and the
    exam blueprint (topics + weights). Pure: same inputs, same forecast.

    Topics on the blueprint with no matching mastery view are treated as
    unknowns (no evidence), which drags readiness down honestly.
    """
    by_topic = {v.topic_id: v for v in views}
    exam_topics = list(blueprint)
    if not exam_topics:
        return ReadinessForecast(
            overall=0.0, coverage=0.0,
            verdict="no exam blueprint provided", topics=(), degraded=degraded,
        )

    total_weight = sum(max(t.weight, 0.0) for t in exam_topics) or 1.0
    results: list[TopicReadiness] = []
    weighted_sum = 0.0
    covered_weight = 0.0
    for et in exam_topics:
        w = max(et.weight, 0.0) / total_weight
        view = by_topic.get(
            et.topic_id,
            TopicMasteryView(topic_id=et.topic_id, has_evidence=False, band="not-started", independence=0.0, revision_due=False),
        )
        tr = _topic_readiness(view, weight=w)
        results.append(tr)
        weighted_sum += tr.readiness * w
        if tr.has_evidence:
            covered_weight += w

    overall = max(0.0, min(1.0, weighted_sum))
    return ReadinessForecast(
        overall=overall,
        coverage=covered_weight,
        verdict=_verdict(overall, covered_weight),
        topics=tuple(results),
        degraded=degraded,
    )


# ---------------------------------------------------------------------------
# Building the mastery views from the CORE engine (via _engine).
# ---------------------------------------------------------------------------
def views_from_engine(
    events: list[Any],
    *,
    subject: Any,
    topic_ids: Iterable[Any],
    graph: Any | None = None,
    asof: datetime | None = None,
) -> list[TopicMasteryView]:
    """Build per-topic mastery views using the CORE intelligence engine.
    Requires ``_engine.available()``.

    A topic's readiness leans on the engine's INDEPENDENCE dimension and on
    whether revision is due (recency-driven, the same forgetting model the
    revision planner uses) and on confirmed gaps — all read, never re-derived.
    """
    from . import _engine

    out: list[TopicMasteryView] = []
    for t in topic_ids:
        proj = _engine.build_topic_projection(events, subject=subject, topic_id=t, graph=graph, asof=asof)
        dims = proj.mastery.reading.dimensions
        # Revision-due mirrors the engine's retention read: recency decayed with
        # real prior evidence. The plain-language flag is on the mastery result.
        revision_due = proj.mastery.plain_language == "revision is due"
        out.append(
            TopicMasteryView(
                topic_id=str(t),
                has_evidence=proj.mastery.observation_count > 0,
                band=proj.mastery.reading.band,
                independence=dims.independence,
                revision_due=revision_due,
                confirmed_gap_types=tuple(g.gap_type for g in proj.gaps if g.confirmed),
            )
        )
    return out
