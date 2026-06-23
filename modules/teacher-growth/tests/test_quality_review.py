"""Quality review: human-owned, teacher-reflects-first, never auto-finalises."""

from __future__ import annotations

import pytest

from app.coaching import EmploymentDecisionError, build_coaching_summary
from app.interaction import Utterance, analyse_interaction
from app.quality_review import (
    QualityReview,
    ReviewFinding,
    ReviewStateError,
    start_review,
)


TEACHER = "tttt0000-0000-4000-8000-000000000001"
REVIEWER = "rrrr0000-0000-4000-8000-000000000002"
OTHER_REVIEWER = "rrrr0000-0000-4000-8000-000000000099"
TEACHER_CONSENT = "cccc0000-0000-4000-8000-000000000007"


def _finding() -> ReviewFinding:
    return ReviewFinding(
        kind="growth_area",
        note="Open up more learner talk.",
        lesson_id="lesson_a",
        evidence="Teacher talk was 85% of speaking time.",
    )


def _happy_path_review() -> QualityReview:
    review = start_review(review_id="rev1", teacher_ref=TEACHER, cycle="2026-T1")
    review.add_finding(_finding())
    review.open_for_teacher_reflection()
    review.submit_teacher_reflection("I agree; I will try think-pair-share.")
    review.record_reviewer_review(
        reviewer_ref=REVIEWER, reviewer_summary="Strong rapport; widen participation."
    )
    return review


def test_full_workflow_reaches_closed_only_via_human_sign_off():
    review = _happy_path_review()
    assert review.state == "awaiting_sign_off"
    review.sign_off(reviewer_ref=REVIEWER)
    assert review.is_closed is True


def test_teacher_reflects_before_reviewer():
    review = start_review(review_id="rev2", teacher_ref=TEACHER, cycle="2026-T1")
    review.open_for_teacher_reflection()
    # The reviewer cannot record a review before the teacher has reflected.
    with pytest.raises(ReviewStateError):
        review.record_reviewer_review(reviewer_ref=REVIEWER, reviewer_summary="x")


def test_sign_off_requires_a_human_reviewer_ref():
    review = _happy_path_review()
    with pytest.raises(PermissionError):
        review.sign_off(reviewer_ref="")


def test_only_the_reviewing_human_can_sign_off():
    review = _happy_path_review()
    with pytest.raises(PermissionError):
        review.sign_off(reviewer_ref=OTHER_REVIEWER)


def test_no_auto_finalisation():
    review = _happy_path_review()
    # The AI never closes a review (employment guard).
    with pytest.raises(EmploymentDecisionError):
        review.auto_finalise()
    assert review.is_closed is False


def test_findings_require_linked_evidence():
    with pytest.raises(ValueError):
        ReviewFinding(kind="strength", note="Great lesson", lesson_id="l", evidence="")


def test_cannot_add_findings_after_sign_off_stage():
    review = _happy_path_review()
    with pytest.raises(ReviewStateError):
        review.add_finding(_finding())


def test_coaching_signal_enters_review_only_with_teacher_consent():
    review = start_review(review_id="rev3", teacher_ref=TEACHER, cycle="2026-T1")
    metrics = analyse_interaction(
        lesson_id="lesson_a",
        teacher_ref=TEACHER,
        utterances=[Utterance(speaker_ref=TEACHER, role="teacher", duration_s=10)],
    )
    signal = build_coaching_summary(metrics).signals[0]
    with pytest.raises(PermissionError):
        review.attach_coaching_signal(signal, teacher_consent_ref="")
    review.attach_coaching_signal(signal, teacher_consent_ref=TEACHER_CONSENT)
    assert review.shared_coaching_signals == [signal]


def test_review_uses_opaque_refs_only():
    review = _happy_path_review()
    review.sign_off(reviewer_ref=REVIEWER)
    # The record carries opaque refs; no name/email field exists on it.
    for attr in ("teacher_ref", "reviewer_ref"):
        assert "@" not in getattr(review, attr)  # not an email.
    assert not hasattr(review, "teacher_name")
    assert not hasattr(review, "teacher_email")
