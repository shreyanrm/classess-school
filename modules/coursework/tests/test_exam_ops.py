"""Exam operations — scheduling, seating, secure print, OMR/scan intake, proctoring.

The hard rules under test:
  - HUMAN-FINAL on everything consequential: scheduling, seating, and proctoring
    sit at RECOMMEND; secure-print sits at PREPARE and releasing it needs explicit
    human approval. Nothing auto-fires.
  - ACCOMMODATIONS are first-class: extra time extends the sitting; separate-room /
    scribe candidates get a room to themselves.
  - NEVER PENALISE SCAN QUALITY: a poor/ambiguous/absent scan routes to a human and
    NEVER reduces a mark (never_penalize_scan is always True).
  - A proctoring signal is a SIGNAL, never a verdict — no automatic action.
  - Everything degrades gracefully with no OCR / proctoring provider.
  - Behavioural data carries only opaque uuids — no PII.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.exam_ops import (
    Accommodation,
    Candidate,
    OMRBubble,
    ProctoringEventKind,
    ProctoringSignal,
    Room,
    ScanQuality,
    SchedulingError,
    SeatingError,
    allocate_seating,
    collect_proctoring,
    intake_scan,
    package_for_secure_print,
    release_secure_print,
    schedule_sitting,
)


def _now() -> datetime:
    return datetime(2030, 1, 1, 9, 0, tzinfo=timezone.utc)


def _candidate(*acc: Accommodation) -> Candidate:
    return Candidate(canonical_uuid=uuid4(), accommodations=frozenset(acc))


# ---------------------------------------------------------------------------
# Scheduling — constraints + accommodation-honouring duration; RECOMMEND.
# ---------------------------------------------------------------------------
def test_schedule_rejects_past_start():
    with pytest.raises(SchedulingError):
        schedule_sitting(
            exam_id=uuid4(),
            starts_at=_now() - timedelta(hours=1),
            base_duration=timedelta(hours=2),
            candidates=[_candidate()],
            now=_now(),
        )


def test_schedule_rejects_non_positive_duration():
    with pytest.raises(SchedulingError):
        schedule_sitting(
            exam_id=uuid4(),
            starts_at=_now() + timedelta(days=1),
            base_duration=timedelta(0),
            candidates=[_candidate()],
            now=_now(),
        )


def test_schedule_standard_duration_without_accommodation():
    sit = schedule_sitting(
        exam_id=uuid4(),
        starts_at=_now() + timedelta(days=1),
        base_duration=timedelta(hours=2),
        candidates=[_candidate()],
        now=_now(),
    )
    assert sit.duration == timedelta(hours=2)
    assert sit.honoured_extra_time is False
    assert sit.ends_at == sit.starts_at + timedelta(hours=2)
    assert sit.rung == "recommend"


def test_schedule_extends_for_longest_extra_time():
    sit = schedule_sitting(
        exam_id=uuid4(),
        starts_at=_now() + timedelta(days=1),
        base_duration=timedelta(hours=2),
        candidates=[_candidate(), _candidate(Accommodation.EXTRA_TIME)],
        now=_now(),
    )
    # 2h * 1.25 = 2.5h, honouring the candidate who needs extra time.
    assert sit.duration == timedelta(hours=2, minutes=30)
    assert sit.honoured_extra_time is True


def test_schedule_can_opt_out_of_extra_time():
    sit = schedule_sitting(
        exam_id=uuid4(),
        starts_at=_now() + timedelta(days=1),
        base_duration=timedelta(hours=2),
        candidates=[_candidate(Accommodation.EXTRA_TIME)],
        honour_extra_time=False,
        now=_now(),
    )
    assert sit.duration == timedelta(hours=2)
    assert sit.honoured_extra_time is False


# ---------------------------------------------------------------------------
# Seating — spacing, separate-room accommodation, capacity overflow; RECOMMEND.
# ---------------------------------------------------------------------------
def test_room_capacity_and_validation():
    assert Room(room_id=uuid4(), rows=3, cols=4).capacity == 12
    with pytest.raises(ValueError):
        Room(room_id=uuid4(), rows=0, cols=4)


def test_seating_requires_a_room():
    with pytest.raises(SeatingError):
        allocate_seating(candidates=[_candidate()], rooms=[])


def test_seating_rejects_negative_spacing():
    with pytest.raises(SeatingError):
        allocate_seating(candidates=[_candidate()], rooms=[Room(room_id=uuid4(), rows=2, cols=2)], spacing=-1)


def test_seating_honours_spacing_gap_between_occupants():
    room = Room(room_id=uuid4(), rows=1, cols=4)
    cands = [_candidate(), _candidate()]
    plan = allocate_seating(candidates=cands, rooms=[room], spacing=1)
    cols = sorted(s.col for s in plan.seats)
    # spacing=1 leaves a gap: columns 0 and 2, never adjacent.
    assert cols == [0, 2]
    assert plan.fully_seated is True
    assert plan.rung == "recommend"


def test_seating_gives_separate_room_candidate_its_own_room():
    room_a = Room(room_id=uuid4(), rows=2, cols=2, label="A")
    room_b = Room(room_id=uuid4(), rows=2, cols=2, label="B")
    sep = _candidate(Accommodation.SEPARATE_ROOM)
    others = [_candidate(), _candidate()]
    plan = allocate_seating(candidates=[sep] + others, rooms=[room_a, room_b], spacing=0)
    sep_seat = next(s for s in plan.seats if s.candidate == sep.canonical_uuid)
    # No other candidate shares the separate candidate's room.
    sharers = [s for s in plan.seats if s.room_id == sep_seat.room_id and s.candidate != sep.canonical_uuid]
    assert sharers == []
    assert plan.fully_seated is True


def test_seating_overflow_is_surfaced_never_double_seated():
    room = Room(room_id=uuid4(), rows=1, cols=2)  # spaced capacity = 1 at spacing=1
    cands = [_candidate(), _candidate(), _candidate()]
    plan = allocate_seating(candidates=cands, rooms=[room], spacing=1)
    # Overflow surfaced, not silently double-seated.
    assert plan.unplaced
    assert plan.fully_seated is False
    seat_coords = [(s.room_id, s.row, s.col) for s in plan.seats]
    assert len(seat_coords) == len(set(seat_coords))  # no two candidates share a seat


# ---------------------------------------------------------------------------
# Secure print — PREPARE; release needs explicit human approval.
# ---------------------------------------------------------------------------
def test_secure_print_package_is_prepared_not_released():
    pkg = package_for_secure_print(
        exam_id=uuid4(), set_label="A", item_prompts=["Q1", "Q2"], serial="SN-1"
    )
    assert pkg.released is False
    assert pkg.released_by is None
    assert pkg.rung == "prepare"
    assert pkg.item_count == 2
    assert pkg.content_hash and pkg.watermark_token  # sealed, but no secret/PII


def test_secure_print_content_hash_is_tamper_evident():
    a = package_for_secure_print(exam_id=uuid4(), set_label="A", item_prompts=["Q1", "Q2"], serial="S")
    b = package_for_secure_print(exam_id=uuid4(), set_label="A", item_prompts=["Q1", "Q2-changed"], serial="S")
    assert a.content_hash != b.content_hash


def test_secure_print_release_requires_human_and_does_not_mutate_original():
    pkg = package_for_secure_print(exam_id=uuid4(), set_label="A", item_prompts=["Q1"], serial="SN-9")
    officer = uuid4()
    released = release_secure_print(pkg, approved_by=officer)
    assert released.released is True
    assert released.released_by == officer
    # The prepared package stands unchanged as audit evidence.
    assert pkg.released is False
    assert pkg.released_by is None
    # Same identity/content; only the release state changed.
    assert released.package_id == pkg.package_id
    assert released.content_hash == pkg.content_hash


# ---------------------------------------------------------------------------
# OMR / scan intake — NEVER penalises scan quality; degrades gracefully.
# ---------------------------------------------------------------------------
class _ClearProvider:
    def read(self, *, image_ref):
        return ScanQuality.CLEAR, [
            OMRBubble(question_index=0, chosen_option="A", read_confidence=0.95),
            OMRBubble(question_index=1, chosen_option="C", read_confidence=0.9),
        ]


class _LowConfidenceProvider:
    """A clear sheet overall, but one bubble read is low-confidence."""

    def read(self, *, image_ref):
        return ScanQuality.CLEAR, [
            OMRBubble(question_index=0, chosen_option="A", read_confidence=0.95),
            OMRBubble(question_index=1, chosen_option="B", read_confidence=0.4),
        ]


class _DegradedProvider:
    def read(self, *, image_ref):
        return ScanQuality.DEGRADED, [
            OMRBubble(question_index=0, chosen_option=None, read_confidence=0.3),
        ]


def test_scan_intake_no_provider_routes_to_human_never_penalises():
    res = intake_scan(submission_ref=uuid4(), image_ref="img://x")
    assert res.quality is ScanQuality.UNREADABLE
    assert res.needs_human_review is True
    assert res.never_penalize_scan is True  # the cardinal rule travels on the wire
    assert res.bubbles == []
    assert "degraded" in res.provider.lower()
    assert res.rung == "recommend"


def test_scan_intake_clean_scan_high_confidence_no_review():
    res = intake_scan(submission_ref=uuid4(), image_ref="img://x", provider=_ClearProvider())
    assert res.quality is ScanQuality.CLEAR
    assert res.needs_human_review is False
    assert res.never_penalize_scan is True
    assert len(res.bubbles) == 2


def test_scan_intake_low_confidence_bubble_routes_sheet_to_human():
    res = intake_scan(submission_ref=uuid4(), image_ref="img://x", provider=_LowConfidenceProvider())
    assert res.needs_human_review is True
    # Even with a low-confidence read, the scan NEVER reduces the mark.
    assert res.never_penalize_scan is True


def test_scan_intake_degraded_quality_routes_to_human_never_penalises():
    res = intake_scan(submission_ref=uuid4(), image_ref="img://x", provider=_DegradedProvider())
    assert res.quality is ScanQuality.DEGRADED
    assert res.needs_human_review is True
    assert res.never_penalize_scan is True
    # The rationale frames scan quality as routing, never a penalty.
    assert "never" in res.rationale.lower() and "mark" in res.rationale.lower()


def test_scan_quality_never_penalised_across_all_qualities():
    # Whatever the quality, never_penalize_scan stays True — scan quality is
    # human-final, never a mark.
    for provider in (None, _ClearProvider(), _LowConfidenceProvider(), _DegradedProvider()):
        res = intake_scan(submission_ref=uuid4(), image_ref="img://x", provider=provider)
        assert res.never_penalize_scan is True


# ---------------------------------------------------------------------------
# Proctoring — a SIGNAL, never a verdict; degrades gracefully; no auto action.
# ---------------------------------------------------------------------------
class _ProctoringProvider:
    def __init__(self, sitting_for: object) -> None:
        self._sitting = sitting_for

    def observe(self, *, sitting_id):
        return [
            ProctoringSignal(
                candidate=uuid4(),
                kind=ProctoringEventKind.MULTIPLE_FACES,
                confidence=0.92,
                at_offset_ms=120000,
                rationale="two faces detected in frame",
            )
        ]


def test_proctoring_no_provider_degrades_to_empty_report_no_auto_action():
    sitting = uuid4()
    report = collect_proctoring(sitting_id=sitting)
    assert report.signals == []
    assert report.flagged is False
    assert report.auto_action_taken is False  # never auto-acts
    assert "degraded" in report.provider.lower()
    assert report.rung == "recommend"


def test_proctoring_signals_are_surfaced_but_never_auto_act():
    sitting = uuid4()
    report = collect_proctoring(sitting_id=sitting, provider=_ProctoringProvider(sitting))
    assert report.flagged is True
    assert len(report.signals) == 1
    # A signal is for a human to review — never an automatic disqualification.
    assert report.auto_action_taken is False
    assert report.signals[0].rung == "recommend"
    assert report.sitting_id == sitting


def test_proctoring_signal_carries_no_verdict_only_a_recommendation():
    sig = ProctoringSignal(
        candidate=uuid4(),
        kind=ProctoringEventKind.FOCUS_LOST,
        confidence=0.7,
        at_offset_ms=5000,
        rationale="focus left the exam window",
    )
    assert sig.rung == "recommend"
