"""Adaptive practice — mistake-based selection, fading support, evidence not a tick."""

from __future__ import annotations

import pytest

from learning import practice
from learning.practice import TopicState, select_for_topic, select_next


def _state(topic, band, indep, *, perf=0.5, obs=5, last="Coach", struggle=False, confirmed=(), proposed=()):
    return TopicState(
        topic_id=topic, band=band, independence=indep, performance=perf,
        observation_count=obs, last_rung_used=last, recent_struggle=struggle,
        confirmed_gap_types=confirmed, proposed_gap_types=proposed,
    )


def test_gap_type_shapes_the_response():
    # Each gap type maps to a DISTINCT response, never generic "more questions".
    proc = select_for_topic(_state("a", "developing", 0.4, confirmed=("procedural",)))
    appn = select_for_topic(_state("a", "developing", 0.4, confirmed=("application",)))
    assert proc.gap_type == "procedural"
    assert appn.gap_type == "application"
    assert proc.gap_response != appn.gap_response


def test_application_gap_stretches_difficulty_up():
    base = select_for_topic(_state("a", "secure", 0.6))
    appn = select_for_topic(_state("a", "secure", 0.6, confirmed=("application",)))
    assert appn.target_difficulty > base.target_difficulty


def test_speed_gap_keeps_difficulty_at_or_below_band():
    base = select_for_topic(_state("a", "secure", 0.6))
    spd = select_for_topic(_state("a", "secure", 0.6, confirmed=("speed",)))
    assert spd.target_difficulty <= base.target_difficulty


def test_prerequisite_gap_is_most_urgent():
    states = [
        _state("a", "developing", 0.4, confirmed=("speed",)),
        _state("b", "developing", 0.4, confirmed=("prerequisite",)),
    ]
    nxt = select_next(states)
    assert nxt.topic_id == "b"
    assert nxt.gap_type == "prerequisite"


def test_difficulty_matches_band_when_no_gap():
    weak = select_for_topic(_state("a", "emerging", 0.2, confirmed=()))
    strong = select_for_topic(_state("a", "secure", 0.6, confirmed=()))
    assert strong.target_difficulty > weak.target_difficulty


def test_support_fades_with_band():
    weak = select_for_topic(_state("a", "emerging", 0.2, last="Coach"))
    strong = select_for_topic(_state("a", "secure", 0.6, last="Coach"))
    # Higher band -> the offered rung carries less help (further down the ladder).
    from learning.ladder import rung_index
    assert rung_index(strong.ladder.rung) >= rung_index(weak.ladder.rung)


def test_support_dependency_gap_forces_a_fade():
    # A support-dependency gap deliberately steps support DOWN to break reliance,
    # even if the learner just struggled.
    sel = select_for_topic(_state("a", "secure", 0.5, last="Coach", struggle=True, confirmed=("support-dependency",)))
    from learning.ladder import rung_index
    assert rung_index(sel.ladder.rung) >= rung_index("Coach")


def test_no_completion_tick_anywhere():
    # Practice contributes evidence, not a completion tick: the selection object
    # has no "completed"/"done" field.
    sel = select_for_topic(_state("a", "developing", 0.4))
    assert not hasattr(sel, "completed")
    assert not hasattr(sel, "done")


def test_selection_carries_helping_or_evaluating_declaration():
    sel = select_for_topic(_state("a", "developing", 0.4))
    assert sel.ladder.mode in ("helping", "evaluating")
    assert sel.ladder.mode_declaration in sel.reason


def test_empty_states_returns_none():
    assert select_next([]) is None


# --- LoopModules: a practice attempt records + emits an evidence event -------
from learning.events import EventEmitter
from .conftest import CONSENT, LEARNER_A, T_EUCLID


def test_record_attempt_emits_evidence_event_feeding_the_engine():
    em = EventEmitter()
    rec = practice.record_practice_attempt(
        canonical_uuid=LEARNER_A, consent_ref=CONSENT, topic_id=T_EUCLID,
        assistance_level="Hint", correct=True, difficulty=0.6, time_taken_ms=30_000, score=0.8,
        emitter=em,
    )
    # It RECORDED an attempt.recorded event (evidence, never a completion tick).
    assert len(em.buffered()) == 1
    env = em.buffered()[0]
    assert env["type"] == "attempt.recorded"
    assert env["payload"]["assistance_level"] == "Hint"
    assert "completed" not in env["payload"] and "done" not in env["payload"]
    assert rec.delivered is False  # degraded in-memory sink in tests
    assert rec.event_id == env["event_id"]


def test_help_rung_attempt_is_never_recorded_as_unaided():
    # No-answer-handover: a correct result on a help rung is SUPPORTED, never an
    # unaided demonstration — the keystone flag is derived from the rung.
    rec = practice.record_practice_attempt(
        canonical_uuid=LEARNER_A, consent_ref=CONSENT, topic_id=T_EUCLID,
        assistance_level="Check-my-work", correct=True, difficulty=0.5, time_taken_ms=10_000,
    )
    assert rec.independent is False
    indep = practice.record_practice_attempt(
        canonical_uuid=LEARNER_A, consent_ref=CONSENT, topic_id=T_EUCLID,
        assistance_level="Independent", correct=True, difficulty=0.5, time_taken_ms=10_000,
    )
    assert indep.independent is True


def test_unknown_rung_is_refused_independence_never_assumed():
    with pytest.raises(ValueError):
        practice.record_practice_attempt(
            canonical_uuid=LEARNER_A, consent_ref=CONSENT, topic_id=T_EUCLID,
            assistance_level="Solo", correct=True, difficulty=0.5, time_taken_ms=10_000,
        )
