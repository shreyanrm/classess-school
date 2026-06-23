"""The rubric library + scoring (B6).

A rubric is the explicit, criterion-by-criterion standard a response is judged
against. Scoring is DETERMINISTIC: given a set of per-criterion point awards, the
rubric collapses them to a normalized [0,1] score the same way every time. The
rubric never invents an opaque single number — the per-criterion breakdown is
always preserved (the same discipline the mastery model applies to learners).

The library ships a small set of reusable, board-agnostic rubrics:

  - ``binary``                 — correct / incorrect (objective items),
  - ``partial_credit``         — graded numeric/procedural work,
  - ``short_answer``           — accuracy + completeness + reasoning,
  - ``extended_response``      — understanding + structure + evidence + clarity,
  - ``project``                — outcome coverage + process + product + reflection.

It ALSO ships the full named library the dossier calls for — the THIRTEEN rubric
TYPES, each board-agnostic, curriculum-alignable, and teacher-editable:

  correctness, process/working, conceptual understanding, competency,
  descriptive, essay/language, diagram, project, practical, oral, coding,
  originality, self-correction.

Each named type is exposed as a factory and through ``RubricType`` /
``rubric_for_type``. A rubric can be ALIGNED to a curriculum slice (an opaque
``OntologyRef``) and EDITED by a teacher (rename a criterion, change its points,
add or remove a criterion) — the platform recommends, the teacher decides.

A rubric is plain language for the learner and the marker. No formulas are
surfaced; the score note explains, in words, what was awarded and why.

Pure. No I/O.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import RubricCriterion, RubricScore


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RubricType(str, Enum):
    """The thirteen named rubric types the dossier calls for. Board-agnostic;
    each is curriculum-alignable and teacher-editable."""

    CORRECTNESS = "correctness"
    PROCESS_WORKING = "process_working"
    CONCEPTUAL_UNDERSTANDING = "conceptual_understanding"
    COMPETENCY = "competency"
    DESCRIPTIVE = "descriptive"
    ESSAY_LANGUAGE = "essay_language"
    DIAGRAM = "diagram"
    PROJECT = "project"
    PRACTICAL = "practical"
    ORAL = "oral"
    CODING = "coding"
    ORIGINALITY = "originality"
    SELF_CORRECTION = "self_correction"


RUBRIC_TYPE_DOCS: dict["RubricType", str] = {}  # filled at the foot of the module


class Rubric(_Model):
    """A named, reusable rubric: an ordered set of criteria.

    ``rubric_type`` records which of the named library types it was minted from
    (None for an ad-hoc/custom rubric). ``aligned_topic_id`` records the opaque
    curriculum slice the rubric was aligned to (curriculum-alignable, never PII).
    Both are optional so a custom or unaligned rubric is still valid.
    """

    rubric_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    criteria: list[RubricCriterion] = Field(min_length=1)
    rubric_type: "RubricType | None" = Field(default=None)
    aligned_topic_id: UUID | None = Field(default=None, description="Opaque ontology topic this rubric is aligned to.")

    @model_validator(mode="after")
    def _coherent(self) -> "Rubric":
        ids = [c.criterion_id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("rubric criteria must have unique criterion_ids.")
        if all(c.max_points <= 0 for c in self.criteria):
            raise ValueError("a rubric must have at least one criterion with positive max_points.")
        return self

    @property
    def total_max_points(self) -> float:
        return sum(c.max_points for c in self.criteria)

    def criterion(self, criterion_id: UUID) -> RubricCriterion | None:
        for c in self.criteria:
            if c.criterion_id == criterion_id:
                return c
        return None

    # -- teacher-editable operations (the platform recommends, the teacher owns) --
    def aligned_to(self, topic_id: UUID) -> "Rubric":
        """Return a copy of this rubric aligned to a curriculum topic slice."""
        return self.model_copy(update={"aligned_topic_id": topic_id})

    def with_criterion(self, criterion: RubricCriterion) -> "Rubric":
        """Return a copy with one extra criterion added (teacher edit)."""
        return self.model_copy(update={"criteria": [*self.criteria, criterion]})

    def without_criterion(self, criterion_id: UUID) -> "Rubric":
        """Return a copy with a criterion removed (teacher edit). Refuses to empty
        the rubric — a rubric must keep at least one criterion."""
        remaining = [c for c in self.criteria if c.criterion_id != criterion_id]
        if not remaining:
            raise ValueError("a rubric must keep at least one criterion.")
        return self.model_copy(update={"criteria": remaining})

    def edit_criterion(
        self,
        criterion_id: UUID,
        *,
        description: str | None = None,
        max_points: float | None = None,
        weight: float | None = None,
    ) -> "Rubric":
        """Return a copy with one criterion's text/points/weight edited (teacher
        edit). Raises KeyError if the criterion is not in the rubric."""
        if self.criterion(criterion_id) is None:
            raise KeyError(f"criterion {criterion_id} not in rubric.")
        new_criteria: list[RubricCriterion] = []
        for c in self.criteria:
            if c.criterion_id == criterion_id:
                new_criteria.append(
                    RubricCriterion(
                        criterion_id=c.criterion_id,
                        description=description if description is not None else c.description,
                        max_points=max_points if max_points is not None else c.max_points,
                        weight=weight if weight is not None else c.weight,
                    )
                )
            else:
                new_criteria.append(c)
        return self.model_copy(update={"criteria": new_criteria})


def _criterion(description: str, max_points: float, weight: float = 1.0) -> RubricCriterion:
    return RubricCriterion(
        criterion_id=uuid4(),
        description=description,
        max_points=max_points,
        weight=weight,
    )


# ---------------------------------------------------------------------------
# Library — reusable, board-agnostic rubric factories.
# ---------------------------------------------------------------------------
def binary_rubric() -> Rubric:
    """Objective correct/incorrect."""
    return Rubric(
        name="Binary",
        description="The response is either correct or it is not.",
        criteria=[_criterion("Correct answer.", max_points=1.0)],
    )


def partial_credit_rubric(max_points: float = 5.0) -> Rubric:
    """Graded numeric/procedural work, awarding method and answer separately so a
    correct method with an arithmetic slip is not scored as a total failure."""
    return Rubric(
        name="Partial credit",
        description="Method and final answer are credited separately.",
        criteria=[
            _criterion("Correct method or approach.", max_points=max_points * 0.6, weight=0.6),
            _criterion("Correct final answer.", max_points=max_points * 0.4, weight=0.4),
        ],
    )


def short_answer_rubric() -> Rubric:
    return Rubric(
        name="Short answer",
        description="A short written response judged on accuracy, completeness, and reasoning.",
        criteria=[
            _criterion("Accuracy of the answer.", max_points=2.0, weight=0.5),
            _criterion("Completeness — all parts addressed.", max_points=1.0, weight=0.25),
            _criterion("Reasoning is shown and sound.", max_points=1.0, weight=0.25),
        ],
    )


def extended_response_rubric() -> Rubric:
    return Rubric(
        name="Extended response",
        description="A longer written response judged on understanding, structure, evidence, and clarity.",
        criteria=[
            _criterion("Demonstrates understanding of the concept.", max_points=4.0, weight=0.4),
            _criterion("Logical structure and organisation.", max_points=2.0, weight=0.2),
            _criterion("Uses relevant evidence or examples.", max_points=2.0, weight=0.2),
            _criterion("Clarity of expression.", max_points=2.0, weight=0.2),
        ],
    )


def project_rubric() -> Rubric:
    return Rubric(
        name="Project",
        description="An extended project judged on outcome coverage, process, product, and reflection.",
        rubric_type=RubricType.PROJECT,
        criteria=[
            _criterion("Covers the targeted learning outcomes.", max_points=4.0, weight=0.35),
            _criterion("Sound process and method.", max_points=3.0, weight=0.25),
            _criterion("Quality of the final product.", max_points=3.0, weight=0.25),
            _criterion("Reflection on what was learned.", max_points=2.0, weight=0.15),
        ],
    )


# ---------------------------------------------------------------------------
# The THIRTEEN named rubric types (the full dossier library). Each is a factory
# tagging the rubric with its ``RubricType`` so the type travels with the rubric.
# ---------------------------------------------------------------------------
def correctness_rubric() -> Rubric:
    return Rubric(
        name="Correctness",
        description="Is the answer right? Objective accuracy of the final result.",
        rubric_type=RubricType.CORRECTNESS,
        criteria=[_criterion("The answer is correct.", max_points=1.0)],
    )


def process_working_rubric(max_points: float = 5.0) -> Rubric:
    """Process / working — credits the METHOD so sound working with a wrong final
    answer still earns partial credit (the dossier's explicit example)."""
    return Rubric(
        name="Process / working",
        description="Credits the method and steps shown, not only the final answer.",
        rubric_type=RubricType.PROCESS_WORKING,
        criteria=[
            _criterion("Chooses an appropriate method.", max_points=max_points * 0.4, weight=0.4),
            _criterion("Steps are shown clearly and in order.", max_points=max_points * 0.4, weight=0.4),
            _criterion("Reaches the correct final answer.", max_points=max_points * 0.2, weight=0.2),
        ],
    )


def conceptual_understanding_rubric() -> Rubric:
    return Rubric(
        name="Conceptual understanding",
        description="Does the response show a correct mental model of the concept?",
        rubric_type=RubricType.CONCEPTUAL_UNDERSTANDING,
        criteria=[
            _criterion("Identifies the underlying concept correctly.", max_points=3.0, weight=0.45),
            _criterion("Applies the concept to the situation.", max_points=2.0, weight=0.3),
            _criterion("Free of misconceptions.", max_points=2.0, weight=0.25),
        ],
    )


def competency_rubric() -> Rubric:
    return Rubric(
        name="Competency",
        description="Demonstrates a transferable competency against its descriptor.",
        rubric_type=RubricType.COMPETENCY,
        criteria=[
            _criterion("Meets the competency descriptor.", max_points=3.0, weight=0.4),
            _criterion("Transfers it to a new or unfamiliar context.", max_points=2.0, weight=0.3),
            _criterion("Performs it independently.", max_points=2.0, weight=0.3),
        ],
    )


def descriptive_rubric() -> Rubric:
    return Rubric(
        name="Descriptive",
        description="A descriptive answer judged on accuracy, detail, and relevance.",
        rubric_type=RubricType.DESCRIPTIVE,
        criteria=[
            _criterion("Factually accurate.", max_points=3.0, weight=0.4),
            _criterion("Sufficient relevant detail.", max_points=2.0, weight=0.3),
            _criterion("Stays on the point asked.", max_points=2.0, weight=0.3),
        ],
    )


def essay_language_rubric() -> Rubric:
    return Rubric(
        name="Essay / language",
        description="Extended writing judged on content, organisation, language, and mechanics.",
        rubric_type=RubricType.ESSAY_LANGUAGE,
        criteria=[
            _criterion("Content and ideas.", max_points=4.0, weight=0.35),
            _criterion("Organisation and structure.", max_points=3.0, weight=0.25),
            _criterion("Language: vocabulary and expression.", max_points=3.0, weight=0.25),
            _criterion("Mechanics: grammar, spelling, punctuation.", max_points=2.0, weight=0.15),
        ],
    )


def diagram_rubric() -> Rubric:
    return Rubric(
        name="Diagram",
        description="A drawn diagram judged on accuracy, labelling, and neatness.",
        rubric_type=RubricType.DIAGRAM,
        criteria=[
            _criterion("Diagram is accurate and complete.", max_points=3.0, weight=0.45),
            _criterion("Parts are correctly labelled.", max_points=2.0, weight=0.35),
            _criterion("Clear and legible.", max_points=1.0, weight=0.2),
        ],
    )


def practical_rubric() -> Rubric:
    return Rubric(
        name="Practical",
        description="A lab/practical task judged on procedure, observation, result, and safety.",
        rubric_type=RubricType.PRACTICAL,
        criteria=[
            _criterion("Follows the correct procedure.", max_points=3.0, weight=0.3),
            _criterion("Records observations accurately.", max_points=3.0, weight=0.3),
            _criterion("Draws a sound result/conclusion.", max_points=2.0, weight=0.2),
            _criterion("Observes safe and correct technique.", max_points=2.0, weight=0.2),
        ],
    )


def oral_rubric() -> Rubric:
    return Rubric(
        name="Oral",
        description="A spoken response judged on content, fluency, and clarity.",
        rubric_type=RubricType.ORAL,
        criteria=[
            _criterion("Content is correct and relevant.", max_points=3.0, weight=0.4),
            _criterion("Fluency and pace.", max_points=2.0, weight=0.3),
            _criterion("Clear pronunciation and delivery.", max_points=2.0, weight=0.3),
        ],
    )


def coding_rubric() -> Rubric:
    return Rubric(
        name="Coding",
        description="A coding task judged on correctness, design, readability, and edge cases.",
        rubric_type=RubricType.CODING,
        criteria=[
            _criterion("Produces correct output / passes the tests.", max_points=4.0, weight=0.4),
            _criterion("Sound design and approach.", max_points=2.0, weight=0.2),
            _criterion("Readable, well-named, and structured.", max_points=2.0, weight=0.2),
            _criterion("Handles edge cases and errors.", max_points=2.0, weight=0.2),
        ],
    )


def originality_rubric() -> Rubric:
    """Originality is scored SEPARATELY from academic correctness (the dossier).
    This rubric never penalises a wrong answer — it judges own-voice authorship."""
    return Rubric(
        name="Originality",
        description="Judges authorship in the learner's own voice — assessed separately from correctness.",
        rubric_type=RubricType.ORIGINALITY,
        criteria=[
            _criterion("Expressed in the learner's own words.", max_points=3.0, weight=0.5),
            _criterion("Sources, where used, are acknowledged.", max_points=2.0, weight=0.3),
            _criterion("Shows independent thinking.", max_points=2.0, weight=0.2),
        ],
    )


def self_correction_rubric() -> Rubric:
    """Self-correction — credits the learner for noticing and fixing their own
    mistake, the metacognitive move the gap engine values."""
    return Rubric(
        name="Self-correction",
        description="Credits recognising a mistake and correcting it independently.",
        rubric_type=RubricType.SELF_CORRECTION,
        criteria=[
            _criterion("Recognises that something is wrong.", max_points=2.0, weight=0.35),
            _criterion("Diagnoses what went wrong.", max_points=2.0, weight=0.3),
            _criterion("Corrects it to a sound result.", max_points=3.0, weight=0.35),
        ],
    )


# Map each named type to its factory (the full thirteen).
_TYPE_FACTORIES: dict[RubricType, "callable"] = {
    RubricType.CORRECTNESS: correctness_rubric,
    RubricType.PROCESS_WORKING: process_working_rubric,
    RubricType.CONCEPTUAL_UNDERSTANDING: conceptual_understanding_rubric,
    RubricType.COMPETENCY: competency_rubric,
    RubricType.DESCRIPTIVE: descriptive_rubric,
    RubricType.ESSAY_LANGUAGE: essay_language_rubric,
    RubricType.DIAGRAM: diagram_rubric,
    RubricType.PROJECT: project_rubric,
    RubricType.PRACTICAL: practical_rubric,
    RubricType.ORAL: oral_rubric,
    RubricType.CODING: coding_rubric,
    RubricType.ORIGINALITY: originality_rubric,
    RubricType.SELF_CORRECTION: self_correction_rubric,
}


def group_project_rubric() -> Rubric:
    """The SIX-dimension group-project rubric the dossier names: contribution,
    collaboration, communication, leadership, quality, and problem-solving. Used
    to grade group projects on both individual contribution and teamwork."""
    return Rubric(
        name="Group project (six dimensions)",
        description="Grades a group project on the six named teamwork dimensions.",
        rubric_type=RubricType.PROJECT,
        criteria=[
            _criterion("Contribution — share of the work carried.", max_points=2.0, weight=1 / 6),
            _criterion("Collaboration — works well with the team.", max_points=2.0, weight=1 / 6),
            _criterion("Communication — shares ideas clearly.", max_points=2.0, weight=1 / 6),
            _criterion("Leadership — guides and supports the team.", max_points=2.0, weight=1 / 6),
            _criterion("Quality — standard of the work produced.", max_points=2.0, weight=1 / 6),
            _criterion("Problem-solving — overcomes obstacles.", max_points=2.0, weight=1 / 6),
        ],
    )


# The six named project dimensions, in order — exposed for callers/UI.
GROUP_PROJECT_DIMENSIONS: tuple[str, ...] = (
    "contribution",
    "collaboration",
    "communication",
    "leadership",
    "quality",
    "problem_solving",
)


def rubric_for_type(rubric_type: RubricType) -> Rubric:
    """A fresh library rubric for one of the thirteen named types."""
    return _TYPE_FACTORIES[rubric_type]()


def full_library() -> dict[RubricType, Rubric]:
    """A fresh instance of every one of the thirteen named-type rubrics."""
    return {rt: factory() for rt, factory in _TYPE_FACTORIES.items()}


RUBRIC_TYPE_DOCS.update(
    {rt: _TYPE_FACTORIES[rt]().description for rt in RubricType}
)


_LIBRARY = {
    "binary": binary_rubric,
    "partial_credit": partial_credit_rubric,
    "short_answer": short_answer_rubric,
    "extended_response": extended_response_rubric,
    "project": project_rubric,
}


def library() -> dict[str, Rubric]:
    """A fresh instance of every library rubric, keyed by handle."""
    return {handle: factory() for handle, factory in _LIBRARY.items()}


def get_rubric(handle: str) -> Rubric:
    """A fresh library rubric by handle. Raises KeyError on an unknown handle."""
    if handle not in _LIBRARY:
        raise KeyError(f"unknown rubric handle: {handle!r}")
    return _LIBRARY[handle]()


# ---------------------------------------------------------------------------
# Scoring — deterministic.
# ---------------------------------------------------------------------------
class ScoredRubric(_Model):
    """The result of scoring a response against a rubric: the per-criterion
    breakdown plus the normalized [0,1] roll-up. The breakdown is always kept."""

    rubric_id: UUID
    scores: list[RubricScore]
    points_awarded: float
    total_max_points: float

    @property
    def normalized(self) -> float:
        if self.total_max_points <= 0:
            return 0.0
        return max(0.0, min(1.0, self.points_awarded / self.total_max_points))


def score_response(rubric: Rubric, awards: dict[UUID, float], *, notes: dict[UUID, str] | None = None) -> ScoredRubric:
    """Score a response against a rubric.

    ``awards`` maps criterion_id -> points awarded. A criterion absent from
    ``awards`` is scored zero (the response did not satisfy it). An award above a
    criterion's max is clamped to the max (a marker can never over-award through
    this path; RubricScore also rejects an explicit over-award upstream).
    """
    notes = notes or {}
    scores: list[RubricScore] = []
    awarded_total = 0.0
    for c in rubric.criteria:
        raw = awards.get(c.criterion_id, 0.0)
        clamped = max(0.0, min(raw, c.max_points))
        awarded_total += clamped
        scores.append(
            RubricScore(
                criterion_id=c.criterion_id,
                points_awarded=clamped,
                max_points=c.max_points,
                note=notes.get(c.criterion_id),
            )
        )
    return ScoredRubric(
        rubric_id=rubric.rubric_id,
        scores=scores,
        points_awarded=awarded_total,
        total_max_points=rubric.total_max_points,
    )
