"""Assignments, quick-checks, and projects — mapped to ontology nodes (B6).

An assignment is coursework an authoring teacher sets against a precise slice of
the curriculum. It is ONTOLOGY-MAPPED, never board-hard-coded: the curriculum is
referenced by opaque ``OntologyRef`` ids (topic / outcome / competency / skill),
so the same assignment shape works for any board the ontology models.

Three shapes, one model with a ``kind`` discriminator:

  - ``quick_check``  — a short, low-stakes pulse (a few items, formative),
  - ``assignment``   — standard homework/classwork (graded coursework),
  - ``project``      — an extended, multi-outcome piece of work.

Creating an assignment from AI-generated content carries the verification block
from the generate-and-verify substrate; an assignment whose items were generated
is only constructable once those items are VERIFIED (see ``papers``). Nothing
here serves unverified generated content.

Pure construction + validation. No I/O. Emitting the ``assignment.created`` event
lives in ``events``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OntologyRef(_Model):
    """Mirror of the events OntologyRef. Board-agnostic: opaque node ids only."""

    topic_id: UUID = Field(description="Ontology topic node.")
    outcome_id: UUID | None = Field(default=None, description="Learning outcome node.")
    competency_id: UUID | None = Field(default=None, description="Competency node.")
    skill_id: UUID | None = Field(default=None, description="Skill node, finest grain.")


class AssignmentKind(str, Enum):
    QUICK_CHECK = "quick_check"
    ASSIGNMENT = "assignment"
    PROJECT = "project"
    # The dossier's additional kinds: homework/worksheets/journals/portfolios.
    HOMEWORK = "homework"
    WORKSHEET = "worksheet"
    JOURNAL = "journal"
    PORTFOLIO = "portfolio"


ASSIGNMENT_KIND_DOCS: dict[AssignmentKind, str] = {
    AssignmentKind.QUICK_CHECK: "A short, low-stakes formative pulse — a few items, fast feedback.",
    AssignmentKind.ASSIGNMENT: "Standard graded coursework — homework or classwork against mapped outcomes.",
    AssignmentKind.PROJECT: "An extended, multi-outcome piece of work demonstrating durable capability.",
    AssignmentKind.HOMEWORK: "Work set to be done outside class against mapped outcomes.",
    AssignmentKind.WORKSHEET: "A structured practice sheet — a set of items on one or a few topics.",
    AssignmentKind.JOURNAL: "An ongoing reflective journal — recurring entries over time, not a single mark.",
    AssignmentKind.PORTFOLIO: "A curated collection of work assembled and revised over time.",
}


class DeliveryMode(str, Enum):
    """How an assignment is delivered and submitted (the dossier's three modes)."""

    ONLINE_DIGITAL = "online_digital"  # answered in-app, digitally
    ONLINE_UPLOAD = "online_upload"  # done off-app, uploaded online
    OFFLINE = "offline"  # done and handed in offline (scanned/entered later)


DELIVERY_MODE_DOCS: dict[DeliveryMode, str] = {
    DeliveryMode.ONLINE_DIGITAL: "Answered directly in the app, digitally.",
    DeliveryMode.ONLINE_UPLOAD: "Completed off-app, then uploaded online.",
    DeliveryMode.OFFLINE: "Completed and handed in offline; captured (scan/entry) later.",
}


class SubmissionMedia(str, Enum):
    """The submission media types a submission may accept (the dossier's set)."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LIVE_CAMERA = "live_camera"


class SubmissionStage(str, Enum):
    """Draft / revision / final tracking. A submission moves DRAFT -> REVISION* ->
    FINAL; only FINAL is a candidate for a consequential mark of record."""

    DRAFT = "draft"
    REVISION = "revision"
    FINAL = "final"


class VerificationCheck(_Model):
    name: str
    passed: bool
    detail: str | None = None


class Verification(_Model):
    """Mirror of the events Verification block — present only when content was
    AI-generated. INVARIANT 7: unverified generated content is never served."""

    status: str = Field(description="pending | passed | failed | human-override")
    confidence: float = Field(ge=0, le=1)
    gate_threshold: float = Field(ge=0, le=1)
    checks: list[VerificationCheck] = Field(default_factory=list)

    @property
    def served(self) -> bool:
        return self.status in ("passed", "human-override")


class AssignmentItem(_Model):
    """One item placed in an assignment. References an ontology question node and
    the outcome it assesses. ``ai_generated`` items must carry verification."""

    item_id: UUID = Field(default_factory=uuid4)
    question_ref: UUID = Field(description="Ontology question node.")
    ontology: OntologyRef
    prompt: str = Field(description="The question text shown to the learner. Plain language.")
    max_points: float = Field(default=1.0, ge=0)
    ai_generated: bool = Field(default=False)
    verification: Verification | None = Field(
        default=None, description="Required when ai_generated is true — only verified items are served."
    )

    @model_validator(mode="after")
    def _generated_must_be_verified(self) -> "AssignmentItem":
        if self.ai_generated:
            if self.verification is None:
                raise ValueError("an AI-generated item must carry a verification block (INVARIANT 7).")
            if not self.verification.served:
                raise ValueError(
                    "an AI-generated item is only placeable once verified (status passed/human-override)."
                )
        return self


class Assignment(_Model):
    """A constructed assignment, ready to be persisted/emitted. Immutable shape;
    creation goes through ``create_assignment`` so invariants hold from line one."""

    assignment_id: UUID = Field(default_factory=uuid4)
    institution_id: UUID = Field(description="Tenant handle (INVARIANT 10 logical isolation).")
    created_by: UUID = Field(description="Opaque ref to the authoring teacher (never PII).")
    kind: AssignmentKind
    title: str
    ontology: OntologyRef = Field(description="The primary node this assignment assesses.")
    items: list[AssignmentItem] = Field(default_factory=list)
    due_at: datetime | None = None
    instructions: str | None = Field(default=None, description="Plain-language instructions for the learner.")
    delivery_mode: DeliveryMode = Field(default=DeliveryMode.ONLINE_DIGITAL)
    accepted_media: list[SubmissionMedia] = Field(
        default_factory=lambda: [SubmissionMedia.TEXT],
        description="Submission media types this assignment accepts.",
    )

    @model_validator(mode="after")
    def _coherent(self) -> "Assignment":
        if not self.title.strip():
            raise ValueError("an assignment needs a title.")
        if not self.accepted_media:
            raise ValueError("an assignment must accept at least one submission media type.")
        # A project is expected to span more than one outcome; a quick-check is
        # expected to be short. These are guidance bounds, not hard limits — the
        # teacher owns the call — so we only reject the clearly-malformed.
        if self.kind is AssignmentKind.QUICK_CHECK and len(self.items) > 10:
            raise ValueError("a quick-check is a short pulse; keep it to 10 items or fewer.")
        return self

    @property
    def total_points(self) -> float:
        return sum(i.max_points for i in self.items)

    @property
    def assessed_topic_ids(self) -> set[UUID]:
        """Every distinct topic this assignment touches, across its items."""
        topics = {self.ontology.topic_id}
        for i in self.items:
            topics.add(i.ontology.topic_id)
        return topics


def create_assignment(
    *,
    institution_id: UUID,
    created_by: UUID,
    kind: AssignmentKind,
    title: str,
    ontology: OntologyRef,
    items: list[AssignmentItem] | None = None,
    due_at: datetime | None = None,
    instructions: str | None = None,
    delivery_mode: DeliveryMode = DeliveryMode.ONLINE_DIGITAL,
    accepted_media: list[SubmissionMedia] | None = None,
    assignment_id: UUID | None = None,
) -> Assignment:
    """Construct an assignment with all invariants enforced.

    Any AI-generated item is validated to carry a passing verification block, so
    an unverified generated item can never enter an assignment.
    """
    return Assignment(
        assignment_id=assignment_id or uuid4(),
        institution_id=institution_id,
        created_by=created_by,
        kind=kind,
        title=title,
        ontology=ontology,
        items=items or [],
        due_at=due_at,
        instructions=instructions,
        delivery_mode=delivery_mode,
        accepted_media=accepted_media or [SubmissionMedia.TEXT],
    )


def quick_check(
    *,
    institution_id: UUID,
    created_by: UUID,
    title: str,
    ontology: OntologyRef,
    items: list[AssignmentItem] | None = None,
) -> Assignment:
    """Convenience constructor for a quick-check."""
    return create_assignment(
        institution_id=institution_id,
        created_by=created_by,
        kind=AssignmentKind.QUICK_CHECK,
        title=title,
        ontology=ontology,
        items=items,
    )


def project(
    *,
    institution_id: UUID,
    created_by: UUID,
    title: str,
    ontology: OntologyRef,
    items: list[AssignmentItem] | None = None,
    due_at: datetime | None = None,
    instructions: str | None = None,
) -> Assignment:
    """Convenience constructor for a project."""
    return create_assignment(
        institution_id=institution_id,
        created_by=created_by,
        kind=AssignmentKind.PROJECT,
        title=title,
        ontology=ontology,
        items=items,
        due_at=due_at,
        instructions=instructions,
    )


def worksheet(
    *,
    institution_id: UUID,
    created_by: UUID,
    title: str,
    ontology: OntologyRef,
    items: list[AssignmentItem] | None = None,
    due_at: datetime | None = None,
    delivery_mode: DeliveryMode = DeliveryMode.ONLINE_DIGITAL,
) -> Assignment:
    """Convenience constructor for a worksheet — a structured practice sheet."""
    return create_assignment(
        institution_id=institution_id,
        created_by=created_by,
        kind=AssignmentKind.WORKSHEET,
        title=title,
        ontology=ontology,
        items=items,
        due_at=due_at,
        delivery_mode=delivery_mode,
    )


def journal(
    *,
    institution_id: UUID,
    created_by: UUID,
    title: str,
    ontology: OntologyRef,
    instructions: str | None = None,
) -> Assignment:
    """Convenience constructor for a reflective journal — recurring text entries,
    accepting text by default (a journal is rarely an objective-item piece)."""
    return create_assignment(
        institution_id=institution_id,
        created_by=created_by,
        kind=AssignmentKind.JOURNAL,
        title=title,
        ontology=ontology,
        instructions=instructions,
        accepted_media=[SubmissionMedia.TEXT, SubmissionMedia.IMAGE],
    )


def portfolio(
    *,
    institution_id: UUID,
    created_by: UUID,
    title: str,
    ontology: OntologyRef,
    instructions: str | None = None,
) -> Assignment:
    """Convenience constructor for a portfolio — a curated, revisable collection,
    accepting a broad set of media (a portfolio gathers varied evidence)."""
    return create_assignment(
        institution_id=institution_id,
        created_by=created_by,
        kind=AssignmentKind.PORTFOLIO,
        title=title,
        ontology=ontology,
        instructions=instructions,
        delivery_mode=DeliveryMode.ONLINE_UPLOAD,
        accepted_media=[
            SubmissionMedia.TEXT,
            SubmissionMedia.IMAGE,
            SubmissionMedia.DOCUMENT,
            SubmissionMedia.AUDIO,
            SubmissionMedia.VIDEO,
        ],
    )


# ---------------------------------------------------------------------------
# Submissions — draft / revision / final tracking, media-typed.
# ---------------------------------------------------------------------------
class SubmissionMediaPart(_Model):
    """One piece of a submission: its media type and an OPAQUE ref to the stored
    artifact (never the bytes, never PII). The actual storage lives outside this
    module; here we only track the media type and the handle."""

    media_type: SubmissionMedia
    artifact_ref: UUID = Field(description="Opaque ref to the stored artifact (storage pipeline owns the bytes).")
    note: str | None = None


class Submission(_Model):
    """A learner's submission to an assignment, with draft/revision/final stage
    tracking. The stage advances DRAFT -> REVISION -> FINAL; the revision count
    travels so the draft/revision history is visible. Only a FINAL submission is
    a candidate for a consequential mark of record (downstream still human-final).

    Carries ONLY opaque refs — ``submitted_by`` is the learner's canonical_uuid,
    never PII; media parts reference stored artifacts by opaque handle."""

    submission_id: UUID = Field(default_factory=uuid4)
    assignment_id: UUID
    submitted_by: UUID = Field(description="Opaque canonical_uuid of the learner — never PII.")
    stage: SubmissionStage = Field(default=SubmissionStage.DRAFT)
    revision_number: int = Field(default=0, ge=0, description="How many revisions before this state.")
    parts: list[SubmissionMediaPart] = Field(default_factory=list)
    submitted_at: datetime | None = Field(default=None, description="Set only when stage is FINAL.")

    @model_validator(mode="after")
    def _stage_rules(self) -> "Submission":
        if self.stage is SubmissionStage.FINAL and self.submitted_at is None:
            raise ValueError("a FINAL submission must carry submitted_at.")
        if self.stage is not SubmissionStage.FINAL and self.submitted_at is not None:
            raise ValueError("only a FINAL submission carries submitted_at.")
        return self

    @property
    def is_final(self) -> bool:
        return self.stage is SubmissionStage.FINAL

    def for_media(self, media_type: SubmissionMedia) -> list[SubmissionMediaPart]:
        return [p for p in self.parts if p.media_type is media_type]

    def revise(self, *, parts: list[SubmissionMediaPart] | None = None) -> "Submission":
        """Advance a draft to a new REVISION (or revise an existing revision),
        bumping the revision count. A FINAL submission cannot be revised — submit
        a fresh draft instead. Returns a new Submission (immutable history)."""
        if self.stage is SubmissionStage.FINAL:
            raise ValueError("a FINAL submission cannot be revised.")
        return self.model_copy(
            update={
                "stage": SubmissionStage.REVISION,
                "revision_number": self.revision_number + 1,
                "parts": parts if parts is not None else self.parts,
            }
        )

    def finalize(self, *, submitted_at: datetime) -> "Submission":
        """Mark the submission FINAL with a submission time. The ONLY path to a
        FINAL submission — a final submission is the candidate for a mark of
        record (the mark itself stays human-final downstream)."""
        return self.model_copy(
            update={"stage": SubmissionStage.FINAL, "submitted_at": submitted_at}
        )


def assignment_accepts(assignment: Assignment, submission: Submission) -> bool:
    """True when every media part of ``submission`` is an accepted media type for
    ``assignment`` — a structural guard so a submission can't carry media the
    assignment never invited."""
    accepted = set(assignment.accepted_media)
    return all(p.media_type in accepted for p in submission.parts)
