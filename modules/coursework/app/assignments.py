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


ASSIGNMENT_KIND_DOCS: dict[AssignmentKind, str] = {
    AssignmentKind.QUICK_CHECK: "A short, low-stakes formative pulse — a few items, fast feedback.",
    AssignmentKind.ASSIGNMENT: "Standard graded coursework — homework or classwork against mapped outcomes.",
    AssignmentKind.PROJECT: "An extended, multi-outcome piece of work demonstrating durable capability.",
}


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

    @model_validator(mode="after")
    def _coherent(self) -> "Assignment":
        if not self.title.strip():
            raise ValueError("an assignment needs a title.")
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
