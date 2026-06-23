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

A rubric is plain language for the learner and the marker. No formulas are
surfaced; the score note explains, in words, what was awarded and why.

Pure. No I/O.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import RubricCriterion, RubricScore


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Rubric(_Model):
    """A named, reusable rubric: an ordered set of criteria."""

    rubric_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    criteria: list[RubricCriterion] = Field(min_length=1)

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
        criteria=[
            _criterion("Covers the targeted learning outcomes.", max_points=4.0, weight=0.35),
            _criterion("Sound process and method.", max_points=3.0, weight=0.25),
            _criterion("Quality of the final product.", max_points=3.0, weight=0.25),
            _criterion("Reflection on what was learned.", max_points=2.0, weight=0.15),
        ],
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
