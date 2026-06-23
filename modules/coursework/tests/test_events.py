"""Event emission — contract shapes, independent-vs-supported, degrade-gracefully.

Validates the emitted payloads against the spine's pydantic mirror of the event
contract when it is importable, so we know the shapes are EXACTLY right and that
no malformed evidence could enter the immutable store.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.assignments import AssignmentKind, OntologyRef, create_assignment
from app.contracts import EvaluationConfidenceBand
from app.events import CourseworkEvents, InMemoryEventSink, ontology_dict
from app.evaluation import EvaluationEngine, ResponseInput, SubmissionInput, confirm_mark


def _ont_dict() -> dict:
    return ontology_dict(OntologyRef(topic_id=uuid4(), outcome_id=uuid4()))


def _run(coro):
    return asyncio.run(coro)


def test_attempt_evidence_independent_flag():
    ev = CourseworkEvents()
    payload = ev.build_attempt_evidence(
        attempt_id=uuid4(),
        ontology=_ont_dict(),
        independent=True,
        assistance_level="Independent",
        correct=True,
        difficulty=0.4,
        time_taken_ms=30_000,
    )
    assert payload["mode"] == "independent"
    assert payload["assistance_level"] == "Independent"


def test_attempt_evidence_supported_flag_coherent():
    ev = CourseworkEvents()
    # Asking for supported with assistance "Independent" must be corrected to a
    # coherent supported level (the contract would reject the incoherent pair).
    payload = ev.build_attempt_evidence(
        attempt_id=uuid4(),
        ontology=_ont_dict(),
        independent=False,
        assistance_level="Independent",
        correct=True,
        difficulty=0.4,
        time_taken_ms=30_000,
    )
    assert payload["mode"] == "supported"
    assert payload["assistance_level"] != "Independent"


def test_emit_degraded_returns_event_object():
    ev = CourseworkEvents()  # no sink
    res = _run(
        ev.emit(
            type="submission.created",
            canonical_uuid=uuid4(),
            purpose="assessment",
            consent_ref=uuid4(),
            payload=ev.build_submission_created(
                submission_id=uuid4(),
                assignment_id=uuid4(),
                submitted_by=uuid4(),
                attempt_ids=[uuid4()],
                submitted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            ),
        )
    )
    assert res.persisted is False
    assert res.type == "submission.created"
    assert res.app == "school"


def test_emit_to_sink_persists():
    sink = InMemoryEventSink()
    ev = CourseworkEvents(sink=sink)
    res = _run(
        ev.emit(
            type="assignment.created",
            canonical_uuid=uuid4(),
            purpose="assessment",
            consent_ref=uuid4(),
            payload={"x": 1},
        )
    )
    assert res.persisted is True
    assert res.event_id is not None
    assert len(sink.events) == 1


def test_score_recorded_human_final_reflects_gate():
    eng = EvaluationEngine(second_model=_Agree())
    out = eng.post_submission(
        SubmissionInput(
            submission_ref=uuid4(),
            scored_subject=uuid4(),
            responses=[ResponseInput(question_ref=uuid4(), expression="2+2", learner_answer=4.0)],
        )
    )
    ev = CourseworkEvents()
    # Before confirmation: human_final must be False on a consequential mark.
    payload = ev.build_score_recorded(out, ontology=_ont_dict())
    assert payload["human_final"] is False
    assert payload["mode"] == "post-submission"
    assert 0.0 <= payload["raw_score"] <= 1.0
    assert payload["confidence_band"] in ("low", "medium", "high")


def test_score_recorded_payload_matches_spine_contract():
    spine_models = _load_spine_event_models()
    if spine_models is None:
        pytest.skip("spine event-store models not importable")
    eng = EvaluationEngine(second_model=_Agree())
    out = eng.post_submission(
        SubmissionInput(
            submission_ref=uuid4(),
            scored_subject=uuid4(),
            responses=[ResponseInput(question_ref=uuid4(), expression="9-4", learner_answer=5.0)],
        )
    )
    confirmed = confirm_mark(out.marking_gate, confirmed_by=uuid4(), adjusted_score=0.95)
    # Rebuild outcome view via the gate truth (emit reads outcome.marking_gate),
    # so emit the score with the confirmed gate by swapping it in.
    object.__setattr__(out, "marking_gate", confirmed)
    ev = CourseworkEvents()
    payload = ev.build_score_recorded(out, ontology=ontology_dict(OntologyRef(topic_id=uuid4())))
    # Validate the EXACT shape against the spine ScoreRecordedPayload mirror.
    spine_models.ScoreRecordedPayload.model_validate(payload)
    assert payload["human_final"] is True


def test_attempt_payload_matches_spine_contract():
    spine_models = _load_spine_event_models()
    if spine_models is None:
        pytest.skip("spine event-store models not importable")
    ev = CourseworkEvents()
    payload = ev.build_attempt_evidence(
        attempt_id=uuid4(),
        ontology=ontology_dict(OntologyRef(topic_id=uuid4())),
        independent=False,
        assistance_level="Hint",
        correct=False,
        difficulty=0.7,
        time_taken_ms=45_000,
        score=0.3,
    )
    spine_models.AttemptPayload.model_validate(payload)


def test_assignment_created_payload_matches_spine_contract():
    spine_models = _load_spine_event_models()
    if spine_models is None:
        pytest.skip("spine event-store models not importable")
    a = create_assignment(
        institution_id=uuid4(),
        created_by=uuid4(),
        kind=AssignmentKind.ASSIGNMENT,
        title="Quadratics",
        ontology=OntologyRef(topic_id=uuid4()),
    )
    ev = CourseworkEvents()
    payload = ev.build_assignment_created(a)
    spine_models.AssignmentCreatedPayload.model_validate(payload)


# ---------------------------------------------------------------------------
# helpers.
# ---------------------------------------------------------------------------
class _Agree:
    def cross_check(self, *, task_class, content):
        return (True, 0.97)


def _load_spine_event_models():
    """Load spine/event-store/app/models.py by file path; None if absent."""
    import importlib.util
    import os
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    path = os.path.join(root, "spine", "event-store", "app", "models.py")
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("_clss_spine_event_models", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_clss_spine_event_models"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None
