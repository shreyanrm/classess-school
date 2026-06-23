"""Pacing drift detection + the teacher knowledge-transfer note."""

from __future__ import annotations

from datetime import date

import pytest

from app.pacing import (
    HandoverNote,
    PacingPlan,
    assess_pacing,
    build_handover_note,
)


def _plan() -> PacingPlan:
    # 40 periods over 20 working days = 2 periods/working day.
    return PacingPlan(
        section_id="S10B",
        subject_id="math",
        planned_periods=40,
        working_days_total=20,
        periods_per_working_day=2.0,
    )


def test_on_track_when_delivered_matches_expected():
    plan = _plan()
    # After 10 working days, 20 periods expected; delivered 20 -> on track.
    status = assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=10, delivered_periods=20)
    assert status.expected_periods == 20.0
    assert status.drift_periods == 0.0
    assert status.band == "on_track"
    assert status.is_drifting is False


def test_behind_when_delivered_lags_expected():
    plan = _plan()
    # After 10 working days, 20 expected; delivered 14 -> drift 6 (30% behind).
    status = assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=10, delivered_periods=14)
    assert status.drift_periods == 6.0
    assert status.band == "behind"
    assert status.is_drifting is True
    assert "drifted" in status.why_am_i_seeing_this
    assert status.consequence_of_ignoring  # plain-language consequence present.


def test_at_risk_when_drift_is_severe():
    plan = _plan()
    # 20 expected, delivered 10 -> 50% behind -> at risk.
    status = assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=10, delivered_periods=10)
    assert status.band == "at_risk"
    assert status.is_drifting is True


def test_ahead_when_delivered_exceeds_expected():
    plan = _plan()
    status = assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=10, delivered_periods=24)
    assert status.drift_periods < 0
    assert status.band == "ahead"
    assert status.is_drifting is False


def test_holidays_do_not_read_as_behind():
    # The denominator is WORKING days, not calendar days. If only 5 working days
    # have elapsed (a holiday-heavy fortnight), only 10 periods are expected — so
    # delivering 10 is on track, not "behind two weeks".
    plan = _plan()
    status = assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=5, delivered_periods=10)
    assert status.expected_periods == 10.0
    assert status.band == "on_track"


def test_expected_is_capped_at_plan_total():
    plan = _plan()
    # More working days than planned cannot expect more than the syllabus length.
    status = assess_pacing(plan, as_of=date(2026, 6, 30), working_days_elapsed=100, delivered_periods=40)
    assert status.expected_periods == 40.0
    assert status.band == "on_track"


def test_handover_note_is_pii_free_and_complete():
    note = build_handover_note(
        section_id="S10B",
        subject_id="math",
        from_teacher_ref="aaaa0000-0000-4000-8000-000000000001",
        reason="planned_leave",
        current_topic_id="topic_quadratics",
        next_topic_id="topic_polynomials",
        last_delivered_period=18,
        watch_points=["Section needs extra practice on factorisation"],
        prepared_materials=["content_pack_7"],
    )
    assert isinstance(note, HandoverNote)
    assert note.is_complete is True
    assert "quadratics" in note.summary()
    # Opaque refs only; the builder takes no name/email field at all.


def test_handover_rejects_non_string_watch_points():
    with pytest.raises(TypeError):
        HandoverNote(
            section_id="S10B",
            subject_id="math",
            from_teacher_ref="aaaa0000-0000-4000-8000-000000000001",
            to_teacher_ref=None,
            reason="substitution",
            current_topic_id="topic_quadratics",
            watch_points=[{"student": "real name"}],  # type: ignore[list-item]
        )
