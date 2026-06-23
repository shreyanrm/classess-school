"""Dashboards — composing the observe -> recommend loop into
"here is what I found, and what to do".

This is the surface the §05 proactive loop becomes. A dashboard turns the spine's
derived state (learner profiles: mastery + confirmed gaps) into a calm, ranked
list of ALERTS, each of which is a fully-provenanced recommendation produced by
the SPINE workflow builders — never minted here. Every alert therefore carries,
by construction:

  - evidence (summary + linked evidence event refs — never an opaque claim),
  - a confidence band,
  - the owner (role + opaque ref),
  - a due date (when time-bound),
  - the consequence of ignoring,
  - the plain-language why-am-i-seeing-this,
  - the suggested action and its permission-ladder stage.

The ladder stage is derived from the action's effect by the spine, so a
dashboard alert can never auto-fire a consequential action (INVARIANT 8): a
finding is surfaced; a human decides and acts.

Headline metrics on the dashboard are resolved through the governed semantic
layer, so the numbers match the quadrant, the forecast, and target analytics.
Nothing here surfaces a raw number/formula to a learner/parent — alerts speak in
plain language and bands.

CONFIDENTIALITY: generic cohort/role labels and opaque refs only. No real names,
no codenames, no board lock-in, no emoji, no exclamation marks.

Deterministic: same profiles in, same dashboard out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from .config import IntelligenceViewsSettings, get_settings
from .semantic_layer import (
    MetricContext,
    MetricValue,
    SemanticLayer,
    build_default_semantic_layer,
)

# Alerts ARE spine recommendations — minted by the spine builder so they carry
# the full provenance set and a ladder stage derived from the action's effect.
# The bridge loads the spine workflow source without an ``app`` name collision.
from .spine_workflow import (
    CohortWeaknessSignal,
    EvidenceRef,
    Recommendation,
    build_cohort_weakness_recommendation,
)

# Display confidence-band order (most-confident first within a status).
_BAND_ORDER = {"high": 0, "medium": 1, "low": 2}

# Map the spine's GapType vocabulary to plain-language topic phrasing already
# lives in the builder; the dashboard only needs the gap_type string, which the
# spine validates against its ten-type set.


@dataclass(frozen=True)
class HeadlineMetric:
    """One metric on the dashboard header, resolved through the semantic layer.

    The dashboard renders ``plain_language``; the raw ``value`` stays internal
    unless the metric is ``learner_safe``."""

    key: str
    label: str
    plain_language: str
    learner_safe: bool
    value: float

    @classmethod
    def of(cls, mv: MetricValue) -> "HeadlineMetric":
        return cls(
            key=mv.key,
            label=mv.label,
            plain_language=mv.plain_language,
            learner_safe=mv.learner_safe,
            value=mv.value,
        )


@dataclass(frozen=True)
class Dashboard:
    """A composed dashboard: headline metrics + ranked alerts.

    ``alerts`` are spine ``Recommendation`` objects, each carrying the full
    explainability set. ``degraded_reasons`` names (never values) the env vars
    whose absence kept the view on its deterministic, in-memory inputs."""

    scope_label: str
    headline: list[HeadlineMetric]
    alerts: list[Recommendation]
    computed_at: datetime
    degraded_reasons: list[str] = field(default_factory=list)

    @property
    def consequential_alerts(self) -> list[Recommendation]:
        """Alerts whose action is consequential — these never auto-fire and wait
        for a human decision."""
        return [a for a in self.alerts if a.is_consequential]

    def alerts_for_owner(self, owner_ref: UUID) -> list[Recommendation]:
        return [a for a in self.alerts if a.owner.ref == owner_ref]


def _evidence_refs_for_topic(profiles: list[Any], topic_id: Any) -> list[EvidenceRef]:
    """Collect linked evidence refs for a topic from confirmed gaps across the
    cohort. Each ref names the attributed event + a one-line plain summary — never
    an opaque claim (the dashboard refuses to surface an alert without these)."""
    refs: list[EvidenceRef] = []
    seen: set[UUID] = set()
    for prof in profiles:
        proj = prof.topic(topic_id)
        if proj is None:
            continue
        for gap in proj.confirmed_gaps:
            for eid in gap.evidence.evidence_event_ids:
                if eid in seen:
                    continue
                seen.add(eid)
                refs.append(
                    EvidenceRef(
                        event_id=eid,
                        summary=(
                            f"Confirmed {gap.gap_type} gap signal on this topic "
                            "(corroborated, not from a single score)."
                        ),
                    )
                )
    return refs


def _dominant_gap_type(profiles: list[Any], topic_id: Any) -> tuple[str, float, int]:
    """The most prevalent CONFIRMED gap type on the topic, its mean confidence,
    and the count of affected learners. Returns ('', 0.0, 0) when none."""
    type_counts: dict[str, int] = {}
    type_conf: dict[str, list[float]] = {}
    affected_learners: dict[str, set[Any]] = {}
    for prof in profiles:
        proj = prof.topic(topic_id)
        if proj is None:
            continue
        for gap in proj.confirmed_gaps:
            gt = gap.gap_type
            type_counts[gt] = type_counts.get(gt, 0) + 1
            type_conf.setdefault(gt, []).append(gap.evidence.confidence)
            affected_learners.setdefault(gt, set()).add(prof.subject)
    if not type_counts:
        return ("", 0.0, 0)
    # Most affected learners, then highest mean confidence, then stable name.
    best = max(
        type_counts,
        key=lambda gt: (
            len(affected_learners[gt]),
            sum(type_conf[gt]) / len(type_conf[gt]),
            gt,
        ),
    )
    mean_conf = sum(type_conf[best]) / len(type_conf[best])
    return (best, mean_conf, len(affected_learners[best]))


def build_topic_alert(
    profiles: list[Any],
    *,
    topic_id: Any,
    topic_label: str,
    cohort_label: str,
    owner_role: str,
    owner_ref: UUID,
    due_date: datetime | None = None,
) -> Recommendation | None:
    """Build ONE dashboard alert for a topic from confirmed cohort gaps.

    The alert is produced by the SPINE cohort-weakness builder, so it carries the
    full provenance set and a ladder stage derived from the action — the view does
    not mint a recommendation. Returns None when there is no confirmed cohort gap
    on the topic (no alert without corroborated evidence)."""
    gap_type, confidence, affected = _dominant_gap_type(profiles, topic_id)
    if not gap_type:
        return None
    evidence = _evidence_refs_for_topic(profiles, topic_id)
    if not evidence:
        return None

    signal = CohortWeaknessSignal(
        cohort_label=cohort_label,
        topic_label=topic_label,
        gap_type=gap_type,
        confidence=confidence,
        evidence=evidence,
        owner_role=owner_role,
        owner_ref=owner_ref,
        learner_count=affected,
        due_date=due_date,
    )
    return build_cohort_weakness_recommendation(signal)


@dataclass(frozen=True)
class TopicSpec:
    """The minimal, PII-free spec a dashboard needs per topic to label an alert."""

    topic_id: Any
    topic_label: str


def compose_dashboard(
    profiles: list[Any],
    topics: list[TopicSpec],
    *,
    cohort_label: str,
    owner_role: str,
    owner_ref: UUID,
    coverage: dict[Any, tuple[float, float]] | None = None,
    effort: dict[Any, float] | None = None,
    due_date: datetime | None = None,
    layer: SemanticLayer | None = None,
    settings: IntelligenceViewsSettings | None = None,
) -> Dashboard:
    """Compose the dashboard: headline metrics + ranked, fully-explainable alerts.

    Every alert is a spine recommendation (full provenance, ladder-classified).
    Headline metrics are resolved through the semantic layer so they match the
    other views. Deterministic over the supplied profiles.
    """
    layer = layer or build_default_semantic_layer()
    settings = settings or get_settings()

    alerts: list[Recommendation] = []
    for spec in topics:
        alert = build_topic_alert(
            profiles,
            topic_id=spec.topic_id,
            topic_label=spec.topic_label,
            cohort_label=cohort_label,
            owner_role=owner_role,
            owner_ref=owner_ref,
            due_date=due_date,
        )
        if alert is not None:
            alerts.append(alert)

    # Rank: most-confident first; consequential alerts surface above safe ones at
    # equal confidence so the human-decision items are seen. (Stable, deterministic.)
    alerts.sort(
        key=lambda a: (
            _BAND_ORDER.get(
                a.confidence_band if isinstance(a.confidence_band, str) else a.confidence_band.value,
                3,
            ),
            not a.is_consequential,
            a.suggested_action,
        )
    )

    # Headline metrics: a calm, cohort-level read across the in-scope topics. We
    # average the topic-grain metrics over the topics that have evidence.
    headline = _headline_metrics(
        profiles, topics, coverage=coverage, effort=effort, layer=layer
    )

    return Dashboard(
        scope_label=cohort_label,
        headline=headline,
        alerts=alerts,
        computed_at=_now(),
        degraded_reasons=settings.degraded_reasons(),
    )


def _headline_metrics(
    profiles: list[Any],
    topics: list[TopicSpec],
    *,
    coverage: dict[Any, tuple[float, float]] | None,
    effort: dict[Any, float] | None,
    layer: SemanticLayer,
) -> list[HeadlineMetric]:
    """Average the topic-grain metrics across in-scope topics into headline reads.

    Each value still comes from the ONE definition in the semantic layer; we only
    aggregate per-topic resolved values into a calm cohort headline."""
    keys = ("topic_mastery", "independence", "confirmed_gap_share", "coverage")
    sums: dict[str, list[float]] = {k: [] for k in keys}
    for spec in topics:
        ctx = MetricContext(
            profiles=profiles,
            topic_id=spec.topic_id,
            extra={"coverage": coverage or {}, "effort": effort or {}},
        )
        # Only count topics any learner has touched, so an untouched topic does
        # not drag the headline to zero.
        if not ctx.topic_projections() and not (coverage or {}).get(spec.topic_id):
            continue
        for k in keys:
            sums[k].append(layer.compute(k, ctx).value)

    headline: list[HeadlineMetric] = []
    for k in keys:
        vals = sums[k]
        avg = sum(vals) / len(vals) if vals else 0.0
        definition = layer.get(k)
        headline.append(
            HeadlineMetric(
                key=k,
                label=definition.label,
                plain_language=definition.plain_language_for(avg),
                learner_safe=definition.learner_safe,
                value=avg,
            )
        )
    return headline


def _now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
