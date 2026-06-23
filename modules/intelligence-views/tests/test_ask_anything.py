"""Ask-anything: governed, one-definition, consent-gated, safety-screened."""

from __future__ import annotations

from app.ask_anything import AskContext, AskRefusalReason, ask
from app.semantic_layer import MetricContext, build_default_semantic_layer
from .conftest import T_TRIG_RATIOS, has_no_emoji


def _ctx(profiles, **kw):
    base = dict(
        profiles=profiles, topic_id=T_TRIG_RATIOS, consent_ok=True,
        safety_screen="allow", purpose="operations",
    )
    base.update(kw)
    return AskContext(**base)


def test_answer_matches_semantic_layer_number(gap_cohort):
    """Ask-anything returns the SAME number the layer computes directly — one
    metric, computed the same everywhere."""
    profiles, topic_id = gap_cohort
    ans = ask("How is mastery on this topic?", _ctx(profiles, audience_is_learner=False))
    assert ans.answered
    assert ans.metric_key == "topic_mastery"
    layer = build_default_semantic_layer()
    direct = layer.compute("topic_mastery", MetricContext(profiles=profiles, topic_id=topic_id, extra={}))
    assert ans.value == direct.value


def test_independence_question_resolves_before_mastery(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("Can they do this without help?", _ctx(profiles, audience_is_learner=False))
    assert ans.metric_key == "independence"


def test_unscreened_question_is_refused(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("How is mastery?", _ctx(profiles, safety_screen=None))
    assert ans.answered is False
    assert ans.refusal_reason == AskRefusalReason.SAFETY_NOT_SCREENED


def test_flagged_question_escalates_to_human(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("a concerning free-text message", _ctx(profiles, safety_screen="flag"))
    assert ans.answered is False
    assert ans.escalated_to_human is True
    assert ans.refusal_reason == AskRefusalReason.SAFETY_FLAGGED


def test_no_consent_is_refused(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("How is mastery?", _ctx(profiles, consent_ok=False))
    assert ans.answered is False
    assert ans.refusal_reason == AskRefusalReason.NO_CONSENT


def test_unknown_metric_is_refused_not_invented(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("what is the cafeteria menu", _ctx(profiles))
    assert ans.answered is False
    assert ans.refusal_reason == AskRefusalReason.UNKNOWN_METRIC
    assert ans.value is None


def test_learner_audience_never_sees_raw_unsafe_number(gap_cohort):
    """A non-learner-safe metric shown to a learner returns plain language only —
    no raw number."""
    profiles, _ = gap_cohort
    ans = ask("How is my mastery?", _ctx(profiles, audience_is_learner=True))
    assert ans.answered
    assert ans.metric_key == "topic_mastery"
    assert ans.value is None  # raw number withheld
    assert ans.plain_language  # plain language given


def test_learner_audience_may_see_learner_safe_number(gap_cohort):
    profiles, topic_id = gap_cohort
    ans = ask(
        "How much has been covered?",
        _ctx(profiles, audience_is_learner=True, coverage={topic_id: (2, 4)}),
    )
    assert ans.answered
    assert ans.metric_key == "coverage"
    assert ans.value is not None  # coverage is learner-safe


def test_answer_carries_definition_and_lineage(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("How is mastery?", _ctx(profiles))
    assert ans.definition
    assert ans.lineage_note
    assert ans.why_am_i_seeing_this


def test_answer_is_deterministic(gap_cohort):
    profiles, _ = gap_cohort
    a = ask("How is mastery?", _ctx(profiles))
    b = ask("How is mastery?", _ctx(profiles))
    assert a.value == b.value and a.plain_language == b.plain_language


def test_answer_text_has_no_emoji_or_exclamation(gap_cohort):
    profiles, _ = gap_cohort
    ans = ask("How is mastery?", _ctx(profiles))
    assert "!" not in ans.plain_language and has_no_emoji(ans.plain_language)
