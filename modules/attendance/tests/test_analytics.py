"""Analytics: rollups over CONFIRMED marks + ranked intervention list.

Analytics is a VIEW layer: it aggregates human-confirmed rolls into attendance
summaries and orders learners by risk for the briefing. It computes, it never
decides — every intervention entry stays ``needs_human_review``.
"""

import datetime as _dt

from app.analytics import (
    AttendanceSummary,
    InterventionEntry,
    cohort_summary,
    intervention_list,
    session_summary,
    subject_summary,
)
from app.capture import capture_manual, confirm_roll
from app.risk import RiskFinding, RiskKind, RiskSeverity


def _finalise(session_id, marks):
    """Build and human-confirm a roll the way the real flow does."""
    draft = capture_manual(session_id, marks)
    return confirm_roll(draft, confirmed_by="uuid-teacher")


# --- session / cohort rollups ---------------------------------------------


def test_session_summary_counts_and_rate():
    roll = _finalise(
        "sess-1",
        {"u1": "present", "u2": "present", "u3": "absent", "u4": "late"},
    )
    summary = session_summary(roll)
    assert isinstance(summary, AttendanceSummary)
    assert summary.scope_id == "sess-1"
    assert summary.present == 2
    assert summary.absent == 1
    assert summary.late == 1
    assert summary.counted == 4
    assert summary.present_like == 3  # present + late
    assert summary.rate == 0.75


def test_excused_counts_as_present_like_not_a_miss():
    roll = _finalise("sess-2", {"u1": "present", "u2": "excused"})
    summary = session_summary(roll)
    # an approved absence is attendance, not a miss -> 100%
    assert summary.excused == 1
    assert summary.rate == 1.0


def test_cohort_summary_sums_across_rolls():
    a = _finalise("sess-a", {"u1": "present", "u2": "absent"})
    b = _finalise("sess-b", {"u3": "present", "u4": "present", "u5": "absent"})
    summary = cohort_summary([a, b], scope_id="class-7B")
    assert summary.scope_id == "class-7B"
    assert summary.present == 3
    assert summary.absent == 2
    assert summary.counted == 5
    assert summary.rate == 0.6


def test_empty_rate_is_none_not_zero():
    summary = cohort_summary([], scope_id="empty")
    # nothing to divide -> rate is undefined, never "0% attendance"
    assert summary.counted == 0
    assert summary.rate is None


# --- per-subject rollup ----------------------------------------------------


def _day(offset, status, subject=None):
    anchor = _dt.date(2026, 6, 22)
    d = (anchor - _dt.timedelta(days=offset)).isoformat()
    entry = {"date": d, "status": status}
    if subject:
        entry["subject"] = subject
    return entry


def test_subject_summary_lowest_rate_first():
    history = {
        "canonical_uuid": "uuid-a",
        "days": [
            _day(1, "absent", "maths"),
            _day(2, "absent", "maths"),
            _day(3, "present", "maths"),  # maths: 1/3 ~ 0.33
            _day(4, "present", "english"),
            _day(5, "present", "english"),  # english: 2/2 = 1.0
        ],
    }
    summaries = subject_summary(history)
    assert [s.scope_id for s in summaries] == ["maths", "english"]
    assert summaries[0].rate == round(1 / 3, 4)
    assert summaries[1].rate == 1.0


def test_subject_summary_groups_unspecified():
    history = {"canonical_uuid": "uuid-a", "days": [_day(1, "present")]}
    summaries = subject_summary(history)
    assert summaries[0].scope_id == "(unspecified)"


# --- intervention list -----------------------------------------------------


def _finding(cuid, kind, severity, confidence=0.8, rationale="why"):
    return RiskFinding(
        canonical_uuid=cuid,
        risk_kind=kind,
        severity=severity,
        confidence=confidence,
        rationale=rationale,
    )


def test_intervention_list_orders_urgent_first():
    findings = [
        _finding("u-watch", RiskKind.PATTERN.value, RiskSeverity.WATCH.value),
        _finding("u-urgent", RiskKind.CONSECUTIVE.value, RiskSeverity.URGENT.value),
        _finding("u-concern", RiskKind.CHRONIC.value, RiskSeverity.CONCERN.value),
    ]
    entries = intervention_list(findings)
    assert [e.canonical_uuid for e in entries] == ["u-urgent", "u-concern", "u-watch"]


def test_intervention_collapses_learner_to_highest_severity():
    findings = [
        _finding("u1", RiskKind.PATTERN.value, RiskSeverity.WATCH.value),
        _finding("u1", RiskKind.CHRONIC.value, RiskSeverity.URGENT.value),
        _finding("u1", RiskKind.EXAM_SHORTAGE.value, RiskSeverity.CONCERN.value),
    ]
    entries = intervention_list(findings)
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, InterventionEntry)
    assert entry.severity == RiskSeverity.URGENT.value  # highest wins
    assert entry.finding_count == 3
    # every contributing kind is preserved, deduped, first-seen order
    assert set(entry.risk_kinds) == {"pattern", "chronic", "exam_shortage"}
    # analytics ranks; a human still owns the response
    assert entry.needs_human_review is True


def test_intervention_list_empty():
    assert intervention_list([]) == []
