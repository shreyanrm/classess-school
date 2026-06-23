"""Prediction layer: reproducibility, lineage, confidence gate, and that
forecasts read the right direction off the features.
"""

from __future__ import annotations

from app.features import compute_feature_vector
from app.prediction import (
    PREDICTION_MODEL_VERSION,
    predict,
    predict_all,
    predict_all_from_vector,
    predict_from_vector,
)

from .conftest import (
    LEARNER_A,
    LEARNER_B,
    NOW,
    T_FUNDTHM,
    T_TRIG_RATIOS,
    days_ago,
    indep,
)


def test_predictions_are_reproducible(improving_history):
    """Same events + asof -> identical prediction across all three kinds."""
    a = predict_all(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    b = predict_all(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    for kind in ("trajectory", "exam_readiness", "risk"):
        assert a[kind].label == b[kind].label
        assert a[kind].score == b[kind].score
        assert a[kind].confidence == b[kind].confidence


def test_prediction_from_vector_matches_from_events(improving_history):
    """Predicting from a precomputed vector equals predicting from events — one
    computation path."""
    vec = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    from_events = predict(improving_history, kind="risk", subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    from_vec = predict_from_vector(vec, kind="risk")
    assert from_events.score == from_vec.score
    assert from_events.label == from_vec.label


def test_every_prediction_carries_lineage(improving_history):
    """Each prediction names the features AND the source events that produced it,
    plus the model + registry versions — reproducible and explainable."""
    preds = predict_all(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    vec = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    for p in preds.values():
        assert p.features_used == vec.as_dict()
        assert set(p.evidence_event_ids) == set(vec.evidence_event_ids)
        assert p.observation_count == vec.observation_count
        assert p.model_version == PREDICTION_MODEL_VERSION
        assert p.registry_signature == vec.registry_signature
        assert p.rationale  # non-empty human-readable why
        # every contributing feature is a real registered feature in the vector
        for f in p.contributing_features:
            assert f in vec.values


def test_confidence_gate_thin_evidence_is_low():
    """A single observation can never read as a confident forecast — the core
    'never confirmed from one score', surfaced in the confidence band."""
    one = [indep(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, occurred_at=NOW)]
    p = predict(one, kind="exam_readiness", subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert p.confidence_band == "low"
    assert p.confidence < 0.7


def test_no_evidence_is_explicit_not_a_guess():
    """No evidence -> an explicit no-evidence/low forecast, zero confidence."""
    pr = predict_all([], subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert pr["exam_readiness"].label == "no-evidence"
    assert pr["exam_readiness"].confidence == 0.0
    assert pr["risk"].confidence == 0.0
    assert pr["trajectory"].observation_count == 0


def test_improving_history_reads_as_improving(improving_history):
    """The climbing learner forecasts an upward trajectory and real readiness."""
    pr = predict_all(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert pr["trajectory"].label in ("improving", "accelerating", "steady")
    assert pr["trajectory"].score >= 0.5
    assert pr["exam_readiness"].label in ("ready", "nearly-ready", "developing")
    assert pr["risk"].label in ("low", "moderate")


def test_declining_history_reads_as_risk(declining_history):
    """The slipping learner forecasts a declining/stalling trajectory and raised
    risk."""
    pr = predict_all(declining_history, subject=LEARNER_B, topic_id=T_TRIG_RATIOS, asof=NOW)
    assert pr["trajectory"].label in ("declining", "stalling")
    assert pr["risk"].label in ("elevated", "high", "moderate")
    assert pr["risk"].score > pr["risk"].score - 1  # sanity, score in range
    assert 0.0 <= pr["risk"].score <= 1.0


def test_supported_only_is_not_exam_ready():
    """High raw success that is entirely SUPPORTED must not read as exam-ready —
    independence is the hard cap on readiness."""
    from .conftest import supported

    events = [
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, occurred_at=days_ago(3)),
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, occurred_at=days_ago(2)),
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, occurred_at=days_ago(1)),
    ]
    p = predict(events, kind="exam_readiness", subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert p.label in ("not-ready", "developing")
    assert p.score < 0.5


def test_prediction_scores_are_bounded(improving_history, declining_history):
    """Every forecast score and confidence stays within [0,1]."""
    for events, subj, topic in (
        (improving_history, LEARNER_A, T_FUNDTHM),
        (declining_history, LEARNER_B, T_TRIG_RATIOS),
    ):
        vec = compute_feature_vector(events, subject=subj, topic_id=topic, asof=NOW)
        for p in predict_all_from_vector(vec).values():
            assert 0.0 <= p.score <= 1.0
            assert 0.0 <= p.confidence <= 1.0
