"""Assignment kinds (worksheet/journal/portfolio), delivery modes, media types,
and draft/revision/final submission tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.assignments import (
    Assignment,
    AssignmentKind,
    DeliveryMode,
    OntologyRef,
    Submission,
    SubmissionMedia,
    SubmissionMediaPart,
    SubmissionStage,
    assignment_accepts,
    journal,
    portfolio,
    worksheet,
)


def _ont() -> OntologyRef:
    return OntologyRef(topic_id=uuid4())


def test_worksheet_kind_and_default_delivery():
    w = worksheet(institution_id=uuid4(), created_by=uuid4(), title="Fractions sheet", ontology=_ont())
    assert w.kind is AssignmentKind.WORKSHEET
    assert w.delivery_mode is DeliveryMode.ONLINE_DIGITAL


def test_journal_accepts_text_and_image():
    j = journal(institution_id=uuid4(), created_by=uuid4(), title="Reading journal", ontology=_ont())
    assert j.kind is AssignmentKind.JOURNAL
    assert SubmissionMedia.TEXT in j.accepted_media
    assert SubmissionMedia.IMAGE in j.accepted_media


def test_portfolio_is_broad_media_upload():
    p = portfolio(institution_id=uuid4(), created_by=uuid4(), title="Year portfolio", ontology=_ont())
    assert p.kind is AssignmentKind.PORTFOLIO
    assert p.delivery_mode is DeliveryMode.ONLINE_UPLOAD
    assert SubmissionMedia.VIDEO in p.accepted_media
    assert SubmissionMedia.DOCUMENT in p.accepted_media


def test_assignment_must_accept_some_media():
    with pytest.raises(ValueError):
        Assignment(
            institution_id=uuid4(),
            created_by=uuid4(),
            kind=AssignmentKind.WORKSHEET,
            title="x",
            ontology=_ont(),
            accepted_media=[],
        )


def test_submission_draft_revision_final_lifecycle():
    s = Submission(
        assignment_id=uuid4(),
        submitted_by=uuid4(),
        parts=[SubmissionMediaPart(media_type=SubmissionMedia.TEXT, artifact_ref=uuid4())],
    )
    assert s.stage is SubmissionStage.DRAFT
    assert s.revision_number == 0
    assert s.is_final is False

    r1 = s.revise()
    assert r1.stage is SubmissionStage.REVISION
    assert r1.revision_number == 1
    r2 = r1.revise()
    assert r2.revision_number == 2

    final = r2.finalize(submitted_at=datetime.now(timezone.utc))
    assert final.is_final is True
    assert final.submitted_at is not None


def test_final_submission_cannot_be_revised():
    s = Submission(assignment_id=uuid4(), submitted_by=uuid4()).finalize(
        submitted_at=datetime.now(timezone.utc)
    )
    with pytest.raises(ValueError):
        s.revise()


def test_final_requires_submitted_at_and_draft_forbids_it():
    with pytest.raises(ValueError):
        Submission(assignment_id=uuid4(), submitted_by=uuid4(), stage=SubmissionStage.FINAL)
    with pytest.raises(ValueError):
        Submission(
            assignment_id=uuid4(),
            submitted_by=uuid4(),
            stage=SubmissionStage.DRAFT,
            submitted_at=datetime.now(timezone.utc),
        )


def test_assignment_accepts_guards_media_type():
    j = journal(institution_id=uuid4(), created_by=uuid4(), title="J", ontology=_ont())
    ok = Submission(
        assignment_id=j.assignment_id,
        submitted_by=uuid4(),
        parts=[SubmissionMediaPart(media_type=SubmissionMedia.TEXT, artifact_ref=uuid4())],
    )
    bad = Submission(
        assignment_id=j.assignment_id,
        submitted_by=uuid4(),
        parts=[SubmissionMediaPart(media_type=SubmissionMedia.VIDEO, artifact_ref=uuid4())],
    )
    assert assignment_accepts(j, ok) is True
    assert assignment_accepts(j, bad) is False  # journal does not accept video


def test_submission_for_media_filters():
    s = Submission(
        assignment_id=uuid4(),
        submitted_by=uuid4(),
        parts=[
            SubmissionMediaPart(media_type=SubmissionMedia.TEXT, artifact_ref=uuid4()),
            SubmissionMediaPart(media_type=SubmissionMedia.IMAGE, artifact_ref=uuid4()),
            SubmissionMediaPart(media_type=SubmissionMedia.IMAGE, artifact_ref=uuid4()),
        ],
    )
    assert len(s.for_media(SubmissionMedia.IMAGE)) == 2
    assert len(s.for_media(SubmissionMedia.TEXT)) == 1
