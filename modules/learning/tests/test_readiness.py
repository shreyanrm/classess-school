"""Exam-readiness forecasting from mastery + coverage."""

from __future__ import annotations

from learning import readiness
from learning.readiness import ExamTopic, TopicMasteryView, forecast


def _view(topic, band, indep, *, evidence=True, revision_due=False, gaps=()):
    return TopicMasteryView(
        topic_id=topic, has_evidence=evidence, band=band,
        independence=indep, revision_due=revision_due, confirmed_gap_types=gaps,
    )


def test_independent_topic_is_exam_ready():
    fc = forecast([_view("a", "independent", 0.9)], [ExamTopic("a")], degraded=True)
    assert fc.overall >= readiness._READY_THRESHOLD
    assert fc.topics[0].risk == "ready"


def test_supported_only_mastery_is_not_ready():
    # Secure band but low independence: an exam is unaided, so it is capped.
    fc = forecast([_view("a", "secure", 0.2)], [ExamTopic("a")], degraded=True)
    assert fc.overall <= readiness._LOW_INDEPENDENCE_CAP
    assert fc.topics[0].risk != "ready"


def test_no_evidence_topic_is_unknown_and_drags_readiness():
    fc = forecast(
        [_view("a", "independent", 0.9)],
        [ExamTopic("a"), ExamTopic("b")],  # b has no view
        degraded=True,
    )
    b = next(t for t in fc.topics if t.topic_id == "b")
    assert b.risk == "unknown"
    assert b.readiness == 0.0
    assert fc.coverage == 0.5


def test_revision_due_lowers_readiness_and_flags_review():
    fc = forecast([_view("a", "independent", 0.9, revision_due=True)], [ExamTopic("a")], degraded=True)
    assert fc.topics[0].risk == "review"
    assert fc.overall < 1.0


def test_confirmed_gap_is_a_risk():
    fc = forecast([_view("a", "secure", 0.7, gaps=("procedural",))], [ExamTopic("a")], degraded=True)
    t = fc.topics[0]
    assert t.risk == "gap"
    assert "procedural" in t.reason


def test_verdict_too_early_when_coverage_low():
    fc = forecast(
        [_view("a", "independent", 0.9)],
        [ExamTopic("a"), ExamTopic("b"), ExamTopic("c"), ExamTopic("d")],
        degraded=True,
    )
    assert fc.coverage < 0.5
    assert "too early" in fc.verdict


def test_weights_change_the_overall():
    views = [_view("a", "independent", 0.9), _view("b", "emerging", 0.1)]
    heavy_a = forecast(views, [ExamTopic("a", 9), ExamTopic("b", 1)], degraded=True)
    heavy_b = forecast(views, [ExamTopic("a", 1), ExamTopic("b", 9)], degraded=True)
    assert heavy_a.overall > heavy_b.overall


def test_next_actions_are_plain_prose_no_numbers():
    fc = forecast(
        [_view("a", "secure", 0.2), _view("b", "independent", 0.9)],
        [ExamTopic("a"), ExamTopic("b")],
        degraded=True,
    )
    actions = fc.next_actions
    assert actions  # the weak topic surfaces an action
    assert all("%" not in a for a in actions)


def test_verdict_headline_is_never_a_percentage():
    fc = forecast([_view("a", "secure", 0.6), _view("b", "secure", 0.6)], [ExamTopic("a"), ExamTopic("b")], degraded=True)
    assert "%" not in fc.verdict
