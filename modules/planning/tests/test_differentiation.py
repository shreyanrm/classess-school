"""Differentiation respects mastery bands."""

import pytest

from planning.app.events import EventLog, EventType
from planning.app.differentiation import (
    Differentiator,
    DifferentiatedTask,
    LearnerReadiness,
    MasteryBand,
    band_for_mastery,
)

SUBJECT = "class-uuid"
OUTCOME = "o1"


def test_band_for_mastery_boundaries():
    assert band_for_mastery(0.0) == MasteryBand.EMERGING
    assert band_for_mastery(0.39) == MasteryBand.EMERGING
    assert band_for_mastery(0.4) == MasteryBand.DEVELOPING
    assert band_for_mastery(0.69) == MasteryBand.DEVELOPING
    assert band_for_mastery(0.7) == MasteryBand.SECURE
    assert band_for_mastery(0.89) == MasteryBand.SECURE
    assert band_for_mastery(0.9) == MasteryBand.EXTENDING
    assert band_for_mastery(1.0) == MasteryBand.EXTENDING


def test_learner_readiness_requires_canonical_uuid():
    with pytest.raises(ValueError):
        LearnerReadiness(canonical_uuid="", outcome_id=OUTCOME, mastery=0.5)


def test_each_learner_gets_band_appropriate_task():
    readiness = [
        LearnerReadiness("u-emerging", OUTCOME, 0.2),
        LearnerReadiness("u-secure", OUTCOME, 0.8),
        LearnerReadiness("u-extending", OUTCOME, 0.95),
    ]
    bank = [
        DifferentiatedTask("t-low", OUTCOME, (MasteryBand.EMERGING, MasteryBand.DEVELOPING), scaffold_level=3),
        DifferentiatedTask("t-mid", OUTCOME, (MasteryBand.SECURE,), scaffold_level=1),
        DifferentiatedTask("t-high", OUTCOME, (MasteryBand.EXTENDING,), scaffold_level=0),
    ]
    plan = Differentiator().assign(OUTCOME, SUBJECT, readiness, bank)
    assert plan.respects_bands()
    assert plan.task_of("u-emerging").task_id == "t-low"
    assert plan.task_of("u-secure").task_id == "t-mid"
    assert plan.task_of("u-extending").task_id == "t-high"


def test_no_cross_band_assignment():
    # Only an EXTENDING task exists; an EMERGING learner must NOT receive it.
    readiness = [LearnerReadiness("u-emerging", OUTCOME, 0.1)]
    bank = [DifferentiatedTask("t-high", OUTCOME, (MasteryBand.EXTENDING,))]
    plan = Differentiator().assign(OUTCOME, SUBJECT, readiness, bank)
    assert plan.band_of("u-emerging") == MasteryBand.EMERGING
    assert plan.task_of("u-emerging") is None  # unmatched, not mis-assigned
    assert plan.respects_bands()  # vacuously true: no wrong assignment exists


def test_task_serves_only_declared_bands():
    task = DifferentiatedTask("t", OUTCOME, (MasteryBand.SECURE,))
    assert task.serves(MasteryBand.SECURE)
    assert not task.serves(MasteryBand.EMERGING)
    assert not task.serves(MasteryBand.EXTENDING)


def test_assign_emits_event_with_band_respect_flag():
    log = EventLog()
    readiness = [LearnerReadiness("u1", OUTCOME, 0.5)]
    bank = [DifferentiatedTask("t", OUTCOME, (MasteryBand.DEVELOPING,))]
    Differentiator(event_log=log).assign(OUTCOME, SUBJECT, readiness, bank)
    ev = log.of_type(EventType.DIFFERENTIATION_GENERATED)[0]
    assert ev.payload["respects_bands"] is True
    assert ev.payload["learner_count"] == 1


def test_other_outcomes_ignored():
    readiness = [
        LearnerReadiness("u1", OUTCOME, 0.5),
        LearnerReadiness("u2", "other-outcome", 0.5),
    ]
    bank = [DifferentiatedTask("t", OUTCOME, (MasteryBand.DEVELOPING,))]
    plan = Differentiator().assign(OUTCOME, SUBJECT, readiness, bank)
    assert plan.band_of("u1") is not None
    assert plan.band_of("u2") is None
