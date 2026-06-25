"""Ask-anything — a GOVERNED semantic-layer query interface.

One metric, defined once, computed the same everywhere. Ask-anything is the
natural-language front door to the SAME registry every dashboard uses: a question
resolves to a metric KEY in the semantic layer, the metric is computed through the
one true definition, and the answer is returned in plain language with its
definition and lineage attached. The interface never invents a number and never
defines a metric inline — it can only ask for metrics that already exist.

GOVERNANCE / SECURITY:
  - INVARIANT 6 (consent): a cross-context read is refused unless a consent +
    purpose check is satisfied. ``AskContext.consent_ok`` carries the result of
    that check (performed by the consent service behind the gateway); absent a
    satisfied check, the query is refused with a clear, PII-free reason.
  - One-metric-one-definition: resolution goes through the registry; an unknown
    metric is refused, not approximated.
  - Learner-safety of numbers: when a metric is not ``learner_safe`` and the
    asker is a learner/parent surface, only the plain-language band is returned —
    never the raw number or the formula.
  - Free-text safety: every question is free text, so the child-safety subsystem
    (moderation / crisis detection / escalation, INVARIANT/child-safety law) must
    screen it. The check is a named, gateway-resolved capability; this module
    enforces that an ALLOW result is present before answering and escalates a
    flagged question to a qualified human instead of answering.

DETERMINISTIC: the built-in keyword resolver maps a question to a metric key with
no model call; a model-assisted resolver (route name only — never a key) is the
optional upgrade and changes nothing about the governance. Same question + same
data -> same answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .config import IntelligenceViewsSettings, get_settings
from .semantic_layer import (
    MetricContext,
    MetricValue,
    SemanticLayer,
    build_default_semantic_layer,
)


class AskRefusalReason(str, Enum):
    NO_CONSENT = "no_consent"
    UNKNOWN_METRIC = "unknown_metric"
    SAFETY_FLAGGED = "safety_flagged"
    SAFETY_NOT_SCREENED = "safety_not_screened"


@dataclass(frozen=True)
class AskContext:
    """The governed context a question is asked in. PII-free.

    ``consent_ok`` is the result of the consent + purpose check (done by the
    consent service behind the gateway). ``audience_is_learner`` gates raw numbers.
    ``safety_screen`` is the child-safety verdict for the free-text question:
    'allow' answers, anything else escalates. ``purpose`` records the declared
    purpose for the audit trail.
    """

    profiles: list[Any]
    topic_id: Any | None = None
    subject: Any | None = None
    consent_ok: bool = False
    audience_is_learner: bool = False
    purpose: str = "operations"
    safety_screen: str | None = None  # "allow" | "flag" | None (not screened)
    coverage: dict[Any, tuple[float, float]] | None = None
    effort: dict[Any, float] | None = None
    asker_role: str = "coordinator"


@dataclass(frozen=True)
class AskAnswer:
    """The answer to a governed question.

    ``answered`` is False when the query was refused (consent, unknown metric, or
    safety). ``plain_language`` is always safe to show; ``value`` is present only
    when the metric is learner-safe OR the audience is not a learner."""

    question: str
    answered: bool
    metric_key: str | None
    label: str | None
    plain_language: str
    definition: str | None
    value: float | None
    lineage_note: str
    why_am_i_seeing_this: str
    refusal_reason: AskRefusalReason | None = None
    escalated_to_human: bool = False
    degraded_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Deterministic question -> metric-key resolution. Keyword rules, no model call.
# A model-assisted resolver (route name only) is the optional upgrade.
# ---------------------------------------------------------------------------
Resolver = Callable[[str, SemanticLayer], str | None]

# Ordered (phrase-set -> metric key). First match wins; order matters so more
# specific reads (independence) are checked before the generic 'mastery'.
_KEYWORD_RULES: list[tuple[frozenset[str], str]] = [
    (frozenset({"independent", "independence", "without help", "on their own"}), "independence"),
    (frozenset({"gap", "gaps", "struggling", "weak", "behind"}), "confirmed_gap_share"),
    (frozenset({"coverage", "covered", "delivered", "syllabus", "planned"}), "coverage"),
    (frozenset({"effort", "engagement", "working", "trying", "practice"}), "effort"),
    (frozenset({"mastery", "master", "doing", "progress", "performance", "how good"}), "topic_mastery"),
]


def keyword_resolver(question: str, layer: SemanticLayer) -> str | None:
    """Map a question to a metric key by keyword. Deterministic. Returns None when
    no defined metric matches — the interface then refuses rather than guessing."""
    q = question.lower()
    for phrases, key in _KEYWORD_RULES:
        if any(phrase in q for phrase in phrases):
            # Only resolve to a metric that actually exists in the registry.
            if key in layer.keys():
                return key
    return None


def _safe_value(mv: MetricValue, audience_is_learner: bool) -> float | None:
    """Return the raw number only when allowed. A non-learner-safe metric shown to
    a learner/parent never exposes the raw number — only the plain-language band."""
    if mv.learner_safe or not audience_is_learner:
        return mv.value
    return None


def ask(
    question: str,
    context: AskContext,
    *,
    layer: SemanticLayer | None = None,
    resolver: Resolver | None = None,
    settings: IntelligenceViewsSettings | None = None,
) -> AskAnswer:
    """Answer a governed question through the semantic layer.

    Order of gates (fail closed): child-safety screen -> consent -> metric
    resolution -> learner-safe number gating. Any failed gate returns a refusal
    with a clear, PII-free reason; a safety flag escalates to a qualified human
    instead of answering.
    """
    layer = layer or build_default_semantic_layer()
    resolver = resolver or keyword_resolver
    settings = settings or get_settings()
    degraded = settings.degraded_reasons()

    # --- Gate 1: child-safety on the free-text question (fail closed) -----
    if context.safety_screen is None:
        return AskAnswer(
            question=question,
            answered=False,
            metric_key=None,
            label=None,
            plain_language=(
                "This question has not been safety-screened yet, so it cannot be "
                "answered. Free-text questions are screened before they are answered."
            ),
            definition=None,
            value=None,
            lineage_note="No metric computed: the question was not screened.",
            why_am_i_seeing_this=(
                "Every free-text question is screened by the child-safety check "
                "before it is answered; this one has not been."
            ),
            refusal_reason=AskRefusalReason.SAFETY_NOT_SCREENED,
            degraded_reasons=degraded,
        )
    if context.safety_screen != "allow":
        return AskAnswer(
            question=question,
            answered=False,
            metric_key=None,
            label=None,
            plain_language=(
                "This question has been routed to a qualified person to look at. "
                "It will not be answered automatically."
            ),
            definition=None,
            value=None,
            lineage_note="No metric computed: the question was escalated.",
            why_am_i_seeing_this=(
                "The child-safety check flagged this question, so it goes to a "
                "qualified human rather than an automated answer."
            ),
            refusal_reason=AskRefusalReason.SAFETY_FLAGGED,
            escalated_to_human=True,
            degraded_reasons=degraded,
        )

    # --- Gate 2: consent + purpose (INVARIANT 6) -------------------------
    if not context.consent_ok:
        return AskAnswer(
            question=question,
            answered=False,
            metric_key=None,
            label=None,
            plain_language=(
                "This cannot be answered without a satisfied consent check for the "
                "stated purpose."
            ),
            definition=None,
            value=None,
            lineage_note="No metric computed: consent check not satisfied.",
            why_am_i_seeing_this=(
                "Every cross-context read is gated by a consent and purpose check; "
                "it was not satisfied for this question."
            ),
            refusal_reason=AskRefusalReason.NO_CONSENT,
            degraded_reasons=degraded,
        )

    # --- Gate 3: resolve to a DEFINED metric (no inline definitions) -----
    key = resolver(question, layer)
    if key is None:
        return AskAnswer(
            question=question,
            answered=False,
            metric_key=None,
            label=None,
            plain_language=(
                "There is no defined measure for that question yet. Measures are "
                "defined once in the shared semantic layer; this interface only "
                "answers with measures that already exist."
            ),
            definition=None,
            value=None,
            lineage_note="No metric matched the question.",
            why_am_i_seeing_this=(
                "The question did not match a measure defined in the shared "
                "semantic layer, so it is not answered (no measure is invented)."
            ),
            refusal_reason=AskRefusalReason.UNKNOWN_METRIC,
            degraded_reasons=degraded,
        )

    # --- Compute through the ONE definition ------------------------------
    ctx = MetricContext(
        profiles=context.profiles,
        topic_id=context.topic_id,
        subject=context.subject,
        extra={"coverage": context.coverage or {}, "effort": context.effort or {}},
    )
    mv = layer.compute(key, ctx)
    value = _safe_value(mv, context.audience_is_learner)

    return AskAnswer(
        question=question,
        answered=True,
        metric_key=mv.key,
        label=mv.label,
        plain_language=f"{mv.label}: {mv.plain_language}.",
        definition=mv.definition,
        value=value,
        lineage_note=(
            "Computed through the shared semantic layer — the same definition "
            "every dashboard uses, so this number matches the other screens."
        ),
        why_am_i_seeing_this=(
            "You asked, the question matched a defined measure, the consent and "
            "safety checks passed, and the measure was computed through its single "
            "definition."
        ),
        degraded_reasons=degraded,
    )


# ---------------------------------------------------------------------------
# Aggregation — one question composed across MANY scopes (the §08 /admin/ask
# dashboard: "Which Grade 8 sections are declining and why?"). The aggregation
# reuses ``ask`` per scope, so EVERY governance gate (safety, consent, one
# definition, learner-safe number gating) holds unchanged for every scope.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AskScope:
    """One scope an aggregated question is answered over (e.g. a section, a
    topic). PII-free: ``label`` is a generic cohort label, never a real name."""

    label: str
    profiles: list[Any]
    topic_id: Any | None = None
    subject: Any | None = None


@dataclass(frozen=True)
class ScopeRow:
    """One row of an aggregated answer: a scope and the measure resolved over it
    through the SAME single definition every other row (and screen) uses."""

    label: str
    answered: bool
    plain_language: str
    value: float | None
    refusal_reason: AskRefusalReason | None = None


@dataclass(frozen=True)
class AskAggregateAnswer:
    """A composed, governed answer across scopes — the ask-anything dashboard.

    Every row resolves the SAME metric key through the one true definition, so the
    rows are comparable and match every other screen. ``rows`` is ranked
    worst-first by default (the dashboard leads with what needs attention).
    ``answered`` is False only when the governance gate that applies to the whole
    request (safety/consent) refused; a per-scope refusal lives on its row."""

    question: str
    answered: bool
    metric_key: str | None
    label: str | None
    definition: str | None
    rows: list[ScopeRow]
    summary: str
    lineage_note: str
    why_am_i_seeing_this: str
    refusal_reason: AskRefusalReason | None = None
    escalated_to_human: bool = False
    degraded_reasons: list[str] = field(default_factory=list)


def ask_aggregate(
    question: str,
    scopes: list[AskScope],
    *,
    consent_ok: bool = False,
    safety_screen: str | None = None,
    audience_is_learner: bool = False,
    purpose: str = "operations",
    asker_role: str = "coordinator",
    coverage: dict[Any, tuple[float, float]] | None = None,
    effort: dict[Any, float] | None = None,
    ascending: bool = True,
    layer: SemanticLayer | None = None,
    resolver: Resolver | None = None,
    settings: IntelligenceViewsSettings | None = None,
) -> AskAggregateAnswer:
    """Answer ONE governed question across many scopes, comparably.

    Composes the §08 ask-anything dashboard: the question is resolved to a single
    metric KEY, then computed for every scope through the one true definition, so
    the rows are directly comparable and agree with every other surface. The
    whole-request governance gates (child-safety, consent) are checked once and
    fail closed for the entire request; a scope that itself fails (e.g. an unknown
    metric) is marked refused on its row rather than fabricated.

    Ranked worst-first by default (``ascending``), so the dashboard leads with the
    scopes that need attention — "which sections are declining" surfaces the
    declining ones at the top. Deterministic: same scopes + data -> same answer.
    """
    layer = layer or build_default_semantic_layer()
    resolver = resolver or keyword_resolver
    settings = settings or get_settings()
    degraded = settings.degraded_reasons()

    # Resolve each scope through the SAME ``ask`` so every governance gate holds
    # identically per scope. The whole-request gates short-circuit on the first
    # scope: child-safety and consent apply to the request, not a single row.
    rows: list[ScopeRow] = []
    metric_key: str | None = None
    label: str | None = None
    definition: str | None = None

    for scope in scopes:
        ctx = AskContext(
            profiles=scope.profiles,
            topic_id=scope.topic_id,
            subject=scope.subject,
            consent_ok=consent_ok,
            audience_is_learner=audience_is_learner,
            purpose=purpose,
            safety_screen=safety_screen,
            coverage=coverage,
            effort=effort,
            asker_role=asker_role,
        )
        ans = ask(question, ctx, layer=layer, resolver=resolver, settings=settings)

        # A whole-request gate (safety / consent) refusing on ANY scope refuses the
        # whole request — these never differ by scope, so fail the request closed.
        if ans.refusal_reason in (
            AskRefusalReason.SAFETY_NOT_SCREENED,
            AskRefusalReason.SAFETY_FLAGGED,
            AskRefusalReason.NO_CONSENT,
        ):
            return AskAggregateAnswer(
                question=question,
                answered=False,
                metric_key=None,
                label=None,
                definition=None,
                rows=[],
                summary=ans.plain_language,
                lineage_note=ans.lineage_note,
                why_am_i_seeing_this=ans.why_am_i_seeing_this,
                refusal_reason=ans.refusal_reason,
                escalated_to_human=ans.escalated_to_human,
                degraded_reasons=degraded,
            )

        if ans.answered:
            metric_key = ans.metric_key
            label = ans.label
            definition = ans.definition
        rows.append(
            ScopeRow(
                label=scope.label,
                answered=ans.answered,
                plain_language=ans.plain_language,
                value=ans.value,
                refusal_reason=ans.refusal_reason,
            )
        )

    # An unknown metric is the same for every scope, so it is a request-level
    # refusal too (nothing was comparable to compose).
    if metric_key is None:
        return AskAggregateAnswer(
            question=question,
            answered=False,
            metric_key=None,
            label=None,
            definition=None,
            rows=[],
            summary=(
                "There is no defined measure for that question yet, so it cannot be "
                "composed across scopes."
            ),
            lineage_note="No metric matched the question.",
            why_am_i_seeing_this=(
                "The question did not match a measure defined in the shared "
                "semantic layer, so no comparable view could be composed."
            ),
            refusal_reason=AskRefusalReason.UNKNOWN_METRIC,
            degraded_reasons=degraded,
        )

    # Rank: rows with a comparable value first, ordered worst-first by default so
    # the dashboard leads with what needs attention. Rows missing a raw value
    # (learner-safe gating) keep their input order at the end — stable + PII-free.
    def _sort_key(r: ScopeRow) -> tuple[int, float, str]:
        if r.value is None:
            return (1, 0.0, r.label)
        v = r.value if ascending else -r.value
        return (0, v, r.label)

    ranked = sorted(rows, key=_sort_key)

    answered_rows = [r for r in ranked if r.answered and r.value is not None]
    if answered_rows:
        lead = answered_rows[0]
        summary = (
            f"Across {len(rows)} scopes for {label}: {lead.label} stands out "
            f"({lead.plain_language})."
        )
    else:
        summary = (
            f"{label} was composed across {len(rows)} scopes; raw values are "
            "withheld for this audience, so each scope is shown in plain language."
        )

    return AskAggregateAnswer(
        question=question,
        answered=True,
        metric_key=metric_key,
        label=label,
        definition=definition,
        rows=ranked,
        summary=summary,
        lineage_note=(
            "Every scope is computed through the shared semantic layer — one "
            "definition, so the scopes are comparable and match the other screens."
        ),
        why_am_i_seeing_this=(
            "You asked one question across several scopes; it matched a defined "
            "measure, the consent and safety checks passed, and the same single "
            "definition was computed for each scope so they can be compared."
        ),
        degraded_reasons=degraded,
    )
