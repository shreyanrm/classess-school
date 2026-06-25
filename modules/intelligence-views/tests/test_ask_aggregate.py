"""Ask-anything aggregation: one governed question composed across many scopes
(the /admin/ask dashboard). Every scope resolves the SAME metric through the one
true definition, so the rows are comparable; every governance gate that guards
``ask`` guards the aggregation unchanged.
"""

from __future__ import annotations

from app.ask_anything import (
    AskAggregateAnswer,
    AskRefusalReason,
    AskScope,
    ask_aggregate,
)
from app.semantic_layer import MetricContext, build_default_semantic_layer
from .conftest import T_TRIG_RATIOS, has_no_emoji


def _scopes(gap_profiles, strong_profiles, topic_id):
    return [
        AskScope(label="Section A (gap)", profiles=gap_profiles, topic_id=topic_id),
        AskScope(label="Section B (strong)", profiles=strong_profiles, topic_id=topic_id),
    ]


def test_aggregate_resolves_same_metric_for_every_scope(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "How is mastery on this topic?",
        _scopes(gp, sp, gt),
        consent_ok=True,
        safety_screen="allow",
    )
    assert isinstance(ans, AskAggregateAnswer)
    assert ans.answered
    assert ans.metric_key == "topic_mastery"
    assert len(ans.rows) == 2
    # Each row's value matches the layer computed directly over its scope — one
    # definition, computed the same everywhere (rows are reordered by rank, so we
    # compare the value SET).
    layer = build_default_semantic_layer()
    values = sorted(r.value for r in ans.rows if r.value is not None)
    direct_gap = layer.compute(
        "topic_mastery", MetricContext(profiles=gp, topic_id=gt, extra={})
    ).value
    direct_strong = layer.compute(
        "topic_mastery", MetricContext(profiles=sp, topic_id=gt, extra={})
    ).value
    assert values == sorted([direct_gap, direct_strong])


def test_aggregate_ranks_worst_first_for_declining_question(gap_cohort, strong_cohort):
    """'Which sections are declining' leads with the weaker section."""
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "Which sections are declining in mastery?",
        _scopes(gp, sp, gt),
        consent_ok=True,
        safety_screen="allow",
        ascending=True,
    )
    assert ans.answered
    # Worst-first: the weaker (gap) section's value <= the stronger section's.
    assert ans.rows[0].value <= ans.rows[-1].value
    assert "Section A (gap)" == ans.rows[0].label


def test_aggregate_unscreened_is_refused(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "How is mastery?", _scopes(gp, sp, gt), consent_ok=True, safety_screen=None
    )
    assert ans.answered is False
    assert ans.refusal_reason == AskRefusalReason.SAFETY_NOT_SCREENED
    assert ans.rows == []


def test_aggregate_flagged_escalates(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "a concerning message", _scopes(gp, sp, gt), consent_ok=True, safety_screen="flag"
    )
    assert ans.answered is False
    assert ans.escalated_to_human is True
    assert ans.refusal_reason == AskRefusalReason.SAFETY_FLAGGED


def test_aggregate_no_consent_is_refused(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "How is mastery?", _scopes(gp, sp, gt), consent_ok=False, safety_screen="allow"
    )
    assert ans.answered is False
    assert ans.refusal_reason == AskRefusalReason.NO_CONSENT


def test_aggregate_unknown_metric_is_refused(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "what is the cafeteria menu",
        _scopes(gp, sp, gt),
        consent_ok=True,
        safety_screen="allow",
    )
    assert ans.answered is False
    assert ans.refusal_reason == AskRefusalReason.UNKNOWN_METRIC


def test_aggregate_learner_audience_withholds_raw_unsafe_values(gap_cohort, strong_cohort):
    """A non-learner-safe metric shown to a learner audience withholds the raw
    value on every row — only plain language is returned, even in aggregate."""
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate(
        "How is mastery?",
        _scopes(gp, sp, gt),
        consent_ok=True,
        safety_screen="allow",
        audience_is_learner=True,
    )
    assert ans.answered
    assert all(r.value is None for r in ans.rows)
    assert all(r.plain_language for r in ans.rows)


def test_aggregate_is_deterministic(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    a = ask_aggregate("How is mastery?", _scopes(gp, sp, gt), consent_ok=True, safety_screen="allow")
    b = ask_aggregate("How is mastery?", _scopes(gp, sp, gt), consent_ok=True, safety_screen="allow")
    assert [(r.label, r.value) for r in a.rows] == [(r.label, r.value) for r in b.rows]
    assert a.summary == b.summary


def test_aggregate_text_has_no_emoji_or_exclamation(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, _ = strong_cohort
    ans = ask_aggregate("How is mastery?", _scopes(gp, sp, gt), consent_ok=True, safety_screen="allow")
    for text in (ans.summary, ans.lineage_note, ans.why_am_i_seeing_this):
        assert "!" not in text and has_no_emoji(text)
