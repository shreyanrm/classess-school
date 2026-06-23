"""Integration with the CORE intelligence engine (spine A3).

The engine is consumed, never modified. These tests run the engine-backed paths
end to end when the engine is importable, and skip cleanly when it is not
(its pydantic dependency absent) — the module's deterministic fallback paths are
covered by the other test files and are the supported paths until a provider is
wired.
"""

from __future__ import annotations

import pytest

from learning import _engine
from learning import practice, readiness

from .conftest import CONSENT, LEARNER_A, NOW, T_EUCLID, days_ago

pytestmark = pytest.mark.skipif(
    not _engine.available(),
    reason=_engine.degraded_reason() or "intelligence engine unavailable",
)


def _attempt_env(topic, *, mode, level, correct, score=None, difficulty=0.5, n=0):
    """A raw attempt.recorded envelope dict the engine can validate."""
    occurred = days_ago(n).isoformat()
    import uuid

    return {
        "event_id": str(uuid.uuid4()),
        "schema_version": "v1",
        "occurred_at": occurred,
        "recorded_at": occurred,
        "app": "school",
        "canonical_uuid": LEARNER_A,
        "purpose": "mastery",
        "consent_ref": CONSENT,
        "type": "attempt.recorded",
        "payload": {
            "attempt_id": str(uuid.uuid4()),
            "ontology": {"topic_id": topic},
            "mode": mode,
            "assistance_level": level,
            "correct": correct,
            "score": score,
            "time_taken_ms": 30_000,
            "difficulty": difficulty,
            "attempt_number": 1,
        },
    }


def test_bridge_compute_mastery_round_trips():
    import uuid

    subject = uuid.UUID(LEARNER_A)
    topic = uuid.UUID(T_EUCLID)
    events = [
        _engine.make_envelope(_attempt_env(T_EUCLID, mode="independent", level="Independent", correct=True, n=3)),
        _engine.make_envelope(_attempt_env(T_EUCLID, mode="independent", level="Independent", correct=True, n=1)),
    ]
    result = _engine.compute_mastery(events, subject=subject, topic_id=topic, asof=NOW)
    # Plain language is what a learner sees — never the formula.
    assert result.plain_language
    assert result.observation_count == 2


def test_practice_selection_from_events_picks_a_topic():
    import uuid

    subject = uuid.UUID(LEARNER_A)
    # All-supported success -> support-dependency territory; selection should
    # surface this topic and fade support.
    events = [
        _engine.make_envelope(_attempt_env(T_EUCLID, mode="supported", level="Coach", correct=True, n=4)),
        _engine.make_envelope(_attempt_env(T_EUCLID, mode="supported", level="Coach", correct=True, n=2)),
    ]
    sel = practice.select_next_from_events(events, subject=subject, topic_ids=[uuid.UUID(T_EUCLID)])
    assert sel is not None
    assert sel.topic_id == T_EUCLID


def test_readiness_views_from_engine():
    import uuid

    subject = uuid.UUID(LEARNER_A)
    events = [
        _engine.make_envelope(_attempt_env(T_EUCLID, mode="independent", level="Independent", correct=True, n=2)),
    ]
    views = readiness.views_from_engine(events, subject=subject, topic_ids=[uuid.UUID(T_EUCLID)])
    assert len(views) == 1 and views[0].has_evidence
    fc = readiness.forecast(views, [readiness.ExamTopic(T_EUCLID)])
    assert 0.0 <= fc.overall <= 1.0
