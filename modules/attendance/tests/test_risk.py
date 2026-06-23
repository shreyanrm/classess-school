"""Risk detection: consecutive, chronic and pattern risks.

These tests target the public risk API. They are written against the
documented contract (see app/risk.py docstring): a ``detect_risks`` entry
point that consumes a per-student attendance history and returns findings,
each carrying a ``risk_kind`` in {"consecutive", "chronic", "pattern"} and
a ``severity``. The detector ASSISTS only - findings are advisory and
carry ``needs_human_review``.

The suite is import-safe: if the optional builder helpers are not present,
the tests construct history with plain dicts, which the detector accepts.
"""

import datetime as _dt

import pytest

risk = pytest.importorskip("app.risk")


def _day(offset, status):
    """A single attendance day, ``offset`` days before a fixed anchor."""
    anchor = _dt.date(2026, 6, 22)
    d = anchor - _dt.timedelta(days=offset)
    return {"date": d.isoformat(), "status": status}


def _history(cuid, days):
    return {"canonical_uuid": cuid, "days": days}


def _kinds(findings):
    return {getattr(f, "risk_kind", None) or f.get("risk_kind") for f in findings}


def test_consecutive_absence_detected():
    # 4 days absent in a row -> consecutive risk.
    days = [_day(i, "absent") for i in range(4)]
    findings = risk.detect_risks(_history("uuid-a", days))
    assert "consecutive" in _kinds(findings)


def test_no_consecutive_when_present_breaks_streak():
    days = [
        _day(0, "absent"),
        _day(1, "present"),
        _day(2, "absent"),
        _day(3, "present"),
    ]
    findings = risk.detect_risks(_history("uuid-a", days))
    assert "consecutive" not in _kinds(findings)


def test_chronic_absence_detected():
    # ~30% absence over a 20-day window -> chronic risk.
    days = []
    for i in range(20):
        days.append(_day(i, "absent" if i % 3 == 0 else "present"))
    findings = risk.detect_risks(_history("uuid-b", days))
    assert "chronic" in _kinds(findings)


def test_healthy_attendance_no_chronic():
    days = [_day(i, "present") for i in range(20)]
    findings = risk.detect_risks(_history("uuid-c", days))
    assert "chronic" not in _kinds(findings)


def test_pattern_risk_detected():
    # Absent on the same weekday repeatedly -> pattern risk.
    # 2026-06-22 is a Monday; pick every Monday going back.
    days = []
    anchor = _dt.date(2026, 6, 22)
    for w in range(6):
        d = anchor - _dt.timedelta(weeks=w)
        days.append({"date": d.isoformat(), "status": "absent"})
    # fill other days present
    for i in range(1, 35):
        d = anchor - _dt.timedelta(days=i)
        if d.weekday() != 0:
            days.append({"date": d.isoformat(), "status": "present"})
    findings = risk.detect_risks(_history("uuid-d", days))
    assert "pattern" in _kinds(findings)


def test_findings_are_advisory_and_pii_free():
    days = [_day(i, "absent") for i in range(5)]
    findings = risk.detect_risks(_history("uuid-a", days))
    assert findings
    for f in findings:
        cuid = getattr(f, "canonical_uuid", None) or f.get("canonical_uuid")
        assert "@" not in cuid
        review = getattr(f, "needs_human_review", None)
        if review is None and isinstance(f, dict):
            review = f.get("needs_human_review")
        assert review is True


def test_empty_history_no_findings():
    findings = risk.detect_risks(_history("uuid-x", []))
    assert list(findings) == []


# --- subject-specific pattern ---------------------------------------------


def test_subject_specific_pattern_detected():
    # Attends overall, but repeatedly skips one subject -> subject pattern.
    days = []
    anchor = _dt.date(2026, 6, 22)
    for i in range(20):
        d = (anchor - _dt.timedelta(days=i)).isoformat()
        # every 3rd day is "maths" and is missed; the rest present in "english"
        if i % 3 == 0:
            days.append({"date": d, "status": "absent", "subject": "maths"})
        else:
            days.append({"date": d, "status": "present", "subject": "english"})
    findings = risk.detect_risks(_history("uuid-s", days))
    pattern = [
        f for f in findings
        if (getattr(f, "risk_kind", None) or f.get("risk_kind")) == "pattern"
    ]
    assert pattern
    # at least one pattern finding is keyed on the subject
    details = [getattr(f, "detail", {}) for f in pattern]
    assert any(d.get("subject") == "maths" for d in details)


# --- exam-shortage (eligibility shortfall before exams) --------------------


def test_exam_shortage_below_floor_is_urgent():
    # 50% attendance against a 75% floor, exam in 10 days -> urgent shortfall.
    days = [_day(i, "present" if i % 2 == 0 else "absent") for i in range(20)]
    findings = risk.detect_risks(
        _history("uuid-e", days),
        exam_eligibility_floor=0.75,
        days_to_exam=10,
    )
    exam = [
        f for f in findings
        if (getattr(f, "risk_kind", None) or f.get("risk_kind")) == "exam_shortage"
    ]
    assert exam
    assert exam[0].severity == "urgent"
    assert exam[0].detail["below_floor"] == "true"


def test_no_exam_shortage_without_floor_or_window():
    days = [_day(i, "present" if i % 2 == 0 else "absent") for i in range(20)]
    # no floor supplied -> detector does not run
    assert not [
        f for f in risk.detect_risks(_history("uuid-e", days))
        if (getattr(f, "risk_kind", None) or f.get("risk_kind")) == "exam_shortage"
    ]
    # exam too far away -> out of window
    far = risk.detect_risks(
        _history("uuid-e", days), exam_eligibility_floor=0.75, days_to_exam=120
    )
    assert not [
        f for f in far
        if (getattr(f, "risk_kind", None) or f.get("risk_kind")) == "exam_shortage"
    ]


def test_exam_shortage_comfortably_above_floor_no_flag():
    days = [_day(i, "present") for i in range(20)]
    findings = risk.detect_risks(
        _history("uuid-e", days), exam_eligibility_floor=0.75, days_to_exam=5
    )
    assert not [
        f for f in findings
        if (getattr(f, "risk_kind", None) or f.get("risk_kind")) == "exam_shortage"
    ]
