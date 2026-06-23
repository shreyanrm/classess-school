"""Mastery model tests — the six dimensions, the multiplicative composite, the
plain-language bands, and the keystone independent-vs-supported distinction."""

from __future__ import annotations

from app.mastery import compute_mastery
from app.models import MasteryWeights

from .conftest import (
    LEARNER_A,
    NOW,
    T_EUCLID,
    days_ago,
    indep,
    score_event,
    supported,
)


def test_dimensions_are_all_in_unit_interval():
    events = [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i)) for i in range(4)]
    res = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    for key in ("performance", "reliability", "independence", "difficulty", "recency", "consistency"):
        v = getattr(res.dimensions, key)
        assert 0.0 <= v <= 1.0


def test_no_evidence_is_not_started():
    res = compute_mastery([], subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    assert res.observation_count == 0
    assert res.reading.band == "not-started"
    assert res.reading.independent is False
    assert res.plain_language == "not started yet"


def test_independent_vs_supported_changes_the_result():
    """THE LOOP: the same number of correct attempts reads very differently when
    they are supported versus independent. Independence caps the product."""
    supported_events = [
        supported(LEARNER_A, T_EUCLID, correct=True, assistance_level="Coach", occurred_at=days_ago(i), difficulty=0.6)
        for i in range(5)
    ]
    independent_events = [
        indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i), difficulty=0.6)
        for i in range(5)
    ]
    sup = compute_mastery(supported_events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    ind = compute_mastery(independent_events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)

    # Independence dimension must separate them sharply.
    assert ind.dimensions.independence > sup.dimensions.independence
    assert sup.dimensions.independence < 0.5
    assert ind.dimensions.independence > 0.9

    # The composite (and thus the band) must be higher for independent work.
    assert ind.reading.composite > sup.reading.composite
    # All-supported success cannot read as independent mastery.
    assert sup.reading.band not in ("independent",)
    assert sup.reading.independent is False
    assert ind.reading.band == "independent"
    assert ind.reading.independent is True


def test_plain_language_never_leaks_the_number_or_formula():
    events = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i)) for i in range(5)]
    res = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    text = res.plain_language.lower()
    assert "you can do this" in text
    # No raw number, no operator, no dimension names in learner copy.
    assert "x" not in text.replace("ex", "")  # no multiplication symbol
    for forbidden in ("performance", "reliability", "composite", "0.", "%"):
        assert forbidden not in text


def test_supported_band_maps_to_with_guidance_language():
    events = [
        supported(LEARNER_A, T_EUCLID, correct=True, assistance_level="Coach", occurred_at=days_ago(i))
        for i in range(4)
    ]
    res = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    assert res.reading.band in ("emerging", "developing")
    assert "guidance" in res.plain_language or "starting" in res.plain_language


def test_single_observation_never_reaches_secure_or_independent():
    res = compute_mastery(
        [indep(LEARNER_A, T_EUCLID, correct=True, difficulty=1.0)],
        subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW,
    )
    assert res.observation_count == 1
    assert res.reading.band not in ("secure", "independent")


def test_recency_decay_lowers_old_evidence_and_flags_revision():
    stale = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(120)) for _ in range(4)]
    fresh = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(1)) for _ in range(4)]
    old = compute_mastery(stale, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    new = compute_mastery(fresh, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    assert old.dimensions.recency < new.dimensions.recency
    assert old.dimensions.recency < 0.4
    assert old.plain_language == "revision is due"


def test_difficulty_dimension_rewards_harder_wins():
    easy = [indep(LEARNER_A, T_EUCLID, correct=True, difficulty=0.1, occurred_at=days_ago(i)) for i in range(4)]
    hard = [indep(LEARNER_A, T_EUCLID, correct=True, difficulty=0.95, occurred_at=days_ago(i)) for i in range(4)]
    e = compute_mastery(easy, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    h = compute_mastery(hard, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    assert h.dimensions.difficulty > e.dimensions.difficulty


def test_reassessment_lifts_mastery():
    """THE LOOP: a weak start, then a strong independent reassessment, lifts the
    reading — the engine is a replay, so later evidence moves the projection."""
    early = [
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.2, occurred_at=days_ago(30)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.3, occurred_at=days_ago(28)),
    ]
    before = compute_mastery(early, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)

    reassessed = early + [
        indep(LEARNER_A, T_EUCLID, correct=True, score=0.95, occurred_at=days_ago(2)),
        indep(LEARNER_A, T_EUCLID, correct=True, score=1.0, occurred_at=days_ago(1)),
        score_event(subject=LEARNER_A, topic_id=T_EUCLID, raw_score=0.95, occurred_at=NOW),
    ]
    after = compute_mastery(reassessed, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)

    assert after.reading.composite > before.reading.composite
    assert after.dimensions.performance > before.dimensions.performance


def test_composite_is_multiplicative_zero_independence_caps_it():
    """A near-zero on any dimension caps the product — the design intent."""
    events = [
        supported(LEARNER_A, T_EUCLID, correct=True, assistance_level="Learn", occurred_at=days_ago(i), difficulty=0.9)
        for i in range(6)
    ]
    res = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    # Fully-scaffolded success: independence near zero, so composite is capped low
    # even though performance is high.
    assert res.dimensions.performance > 0.8
    assert res.dimensions.independence < 0.2
    assert res.reading.composite < 0.3


def test_weights_are_honored_but_shape_is_stable():
    events = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i), difficulty=0.6) for i in range(5)]
    base = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    # Emphasizing independence (exponent 1) vs softening it (smaller exponent)
    # raises the composite when independence is high.
    soft = MasteryWeights(independence=0.5)
    softened = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, weights=soft, asof=NOW)
    assert softened.reading.composite >= base.reading.composite


def test_determinism_same_events_same_reading():
    events = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i)) for i in range(4)]
    a = compute_mastery(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    b = compute_mastery(list(reversed(events)), subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    assert a.reading.model_dump() == b.reading.model_dump()
    assert a.evidence_event_ids != []  # lineage present
