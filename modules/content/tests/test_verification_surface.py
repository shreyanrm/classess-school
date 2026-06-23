"""Verification surface: confidence banding + the human-approval permission ladder."""

import content
from content.repository import (
    ApprovalState,
    ApprovalTransitionError,
    ContentKind,
    InMemoryContentRepository,
    LicenceMetadata,
)
from content.verification_surface import (
    ConfidenceBand,
    ReviewDecision,
    ReviewQueue,
    ReviewVerdict,
    band_for_confidence,
)

import pytest


def _draft(repo, *, verified):
    return repo.create(
        topic_id="topic-1", kind=ContentKind.WORKED_EXAMPLE, title="Example",
        body={"answer": 1}, licence=LicenceMetadata.for_generated(),
        author="system:generate", verified_served=verified,
    )


def test_band_for_confidence():
    assert band_for_confidence(served=True, confidence=0.99, gate_threshold=0.85) is ConfidenceBand.GREEN
    assert band_for_confidence(served=True, confidence=0.88, gate_threshold=0.85) is ConfidenceBand.AMBER
    assert band_for_confidence(served=False, confidence=0.99, gate_threshold=0.85) is ConfidenceBand.RED
    assert band_for_confidence(served=True, confidence=0.99, gate_threshold=0.85, verified=False) is ConfidenceBand.RED


def test_enqueue_moves_to_in_review_and_bands():
    repo = InMemoryContentRepository()
    rec = _draft(repo, verified=True)
    q = ReviewQueue(repo)
    item = q.enqueue(
        rec.content_id, served_by_gate=True, verified=True,
        confidence=0.99, gate_threshold=0.85,
    )
    assert item.band is ConfidenceBand.GREEN
    assert repo.require(rec.content_id).approval_state is ApprovalState.IN_REVIEW


def test_approve_decision_promotes_verified_content():
    repo = InMemoryContentRepository()
    rec = _draft(repo, verified=True)
    q = ReviewQueue(repo)
    item = q.enqueue(rec.content_id, served_by_gate=True, verified=True, confidence=0.99, gate_threshold=0.85)
    resolved = q.decide(ReviewDecision(item_id=item.item_id, verdict=ReviewVerdict.APPROVE, reviewer="reviewer:hod"))
    assert resolved.resolved is True
    updated = repo.require(rec.content_id)
    assert updated.approval_state is ApprovalState.APPROVED
    assert updated.is_servable is True


def test_approve_refuses_unverified_content():
    """The permission-ladder approval still cannot serve unverified content."""
    repo = InMemoryContentRepository()
    rec = _draft(repo, verified=False)
    q = ReviewQueue(repo)
    item = q.enqueue(
        rec.content_id, served_by_gate=False, verified=False,
        confidence=0.0, gate_threshold=0.85, review_reason="ingested; unverified",
    )
    assert item.band is ConfidenceBand.RED
    with pytest.raises(ApprovalTransitionError):
        q.decide(ReviewDecision(item_id=item.item_id, verdict=ReviewVerdict.APPROVE, reviewer="reviewer:hod"))


def test_reject_and_revise():
    repo = InMemoryContentRepository()
    rec = _draft(repo, verified=True)
    q = ReviewQueue(repo)
    item = q.enqueue(rec.content_id, served_by_gate=True, verified=True, confidence=0.9, gate_threshold=0.85)
    resolved = q.decide(ReviewDecision(item_id=item.item_id, verdict=ReviewVerdict.REJECT, reviewer="reviewer:hod"))
    assert resolved.resolved is True
    assert repo.require(rec.content_id).approval_state is ApprovalState.REJECTED


def test_pending_orders_red_first():
    repo = InMemoryContentRepository()
    green = _draft(repo, verified=True)
    red = _draft(repo, verified=False)
    q = ReviewQueue(repo)
    q.enqueue(green.content_id, served_by_gate=True, verified=True, confidence=0.99, gate_threshold=0.85)
    q.enqueue(red.content_id, served_by_gate=False, verified=False, confidence=0.0, gate_threshold=0.85)
    pending = q.pending()
    assert pending[0].band is ConfidenceBand.RED


def test_defer_leaves_item_pending():
    repo = InMemoryContentRepository()
    rec = _draft(repo, verified=True)
    q = ReviewQueue(repo)
    item = q.enqueue(rec.content_id, served_by_gate=True, verified=True, confidence=0.9, gate_threshold=0.85)
    same = q.decide(ReviewDecision(item_id=item.item_id, verdict=ReviewVerdict.DEFER, reviewer="reviewer:hod"))
    assert same.resolved is False
    assert q.get(item.item_id).resolved is False


def test_no_double_resolution():
    repo = InMemoryContentRepository()
    rec = _draft(repo, verified=True)
    q = ReviewQueue(repo)
    item = q.enqueue(rec.content_id, served_by_gate=True, verified=True, confidence=0.99, gate_threshold=0.85)
    q.decide(ReviewDecision(item_id=item.item_id, verdict=ReviewVerdict.APPROVE, reviewer="reviewer:hod"))
    with pytest.raises(ValueError):
        q.decide(ReviewDecision(item_id=item.item_id, verdict=ReviewVerdict.REJECT, reviewer="reviewer:hod"))
