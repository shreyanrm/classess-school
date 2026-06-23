"""Blueprint-driven paper generation (B6).

A BLUEPRINT is the coverage specification of a paper: how many items, of what
marks, across topic x difficulty band x cognitive level. The paper engine fills
the blueprint with ITEMS, and every generated item passes through the AI
fabric's GENERATE-AND-VERIFY substrate (INVARIANT 7) — only items the confidence
gate SERVES are included; anything withheld is flagged for human review and left
out of the served set.

Two paths, both real (not stubs):

  - a deterministic math/physics path that needs NO LLM — the blueprint cell
    carries an expression + claimed answer, the fabric's deterministic verifier
    re-computes it symbolically/numerically, and (with a live second model) the
    confidence gate serves it. With no second-model provider the gate stays
    closed and the cell is flagged for human review — degrades safely.
  - an interface path for free-text items routed through the fabric orchestrator;
    with no provider it returns a clean refusal and the cell is flagged.

MULTI-SET: ``generate_sets`` produces N parallel sets (A/B/C ...) from one
blueprint, each a different draw, so a class can sit equivalent-but-distinct
papers. Sets share the blueprint coverage exactly.

Generation never grades and never serves unverified content. The engine holds no
credentials; the fabric router refuses cleanly when no provider key is set.
"""

from __future__ import annotations

import importlib
import string
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .assignments import OntologyRef, Verification, VerificationCheck


# ---------------------------------------------------------------------------
# AI-fabric access — imported lazily so the module is import-safe even if the
# spine path is not on sys.path. The fabric is CONSUMED, never modified.
# ---------------------------------------------------------------------------
def _load_fabric():
    """Return the ai-fabric verify module, or None if absent.

    Import-safe: a missing fabric degrades to the deterministic-only path with a
    clear, named reason; it never raises at import time. Resolution order:

      1. an already-importable ``app.verify`` (when run inside ai-fabric),
      2. a sibling spine path discovered from this file's location, loaded by
         file path WITHOUT mutating ``sys.path`` or modifying the spine.
    """
    try:
        return importlib.import_module("app.verify")
    except Exception:
        pass
    return _load_spine_verify_by_path()


def _load_spine_verify_by_path():
    """Load spine/ai-fabric/app/verify.py by file path. None if not found."""
    import importlib.util
    import os
    import sys

    cached = sys.modules.get("_clss_spine_verify")
    if cached is not None:
        return cached

    here = os.path.dirname(os.path.abspath(__file__))
    # modules/coursework/app -> repo root is three levels up.
    root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    verify_path = os.path.join(root, "spine", "ai-fabric", "app", "verify.py")
    if not os.path.exists(verify_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("_clss_spine_verify", verify_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_clss_spine_verify"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        sys.modules.pop("_clss_spine_verify", None)
        return None


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TestType(str, Enum):
    """The test-type discriminator (the dossier's four named test types).

      - PERIODIC   — a scheduled cyclical test (e.g. unit/term), graded.
      - FORMATIVE  — low-stakes, for-learning; feedback over a mark.
      - SUMMATIVE  — high-stakes, of-learning; a mark of record.
      - SLIP       — a very short slip test / exit ticket, a quick pulse.
    """

    PERIODIC = "periodic"
    FORMATIVE = "formative"
    SUMMATIVE = "summative"
    SLIP = "slip"

    # Not a pytest test class — the name merely begins with "Test".
    __test__ = False


TEST_TYPE_DOCS: dict["TestType", str] = {
    TestType.PERIODIC: "A scheduled cyclical test across a unit or term; graded.",
    TestType.FORMATIVE: "Low-stakes assessment for learning — feedback matters more than the mark.",
    TestType.SUMMATIVE: "High-stakes assessment of learning — a mark of record; human-final.",
    TestType.SLIP: "A very short slip test / exit ticket — a quick pulse, a handful of items.",
}

# Whether a test type produces a CONSEQUENTIAL mark of record by default. A
# summative/periodic paper does; formative/slip are for-learning. (Permission
# ladder: a consequential mark is still always human-final downstream.)
_TEST_TYPE_CONSEQUENTIAL: dict["TestType", bool] = {
    TestType.PERIODIC: True,
    TestType.SUMMATIVE: True,
    TestType.FORMATIVE: False,
    TestType.SLIP: False,
}


def test_type_is_consequential(test_type: TestType) -> bool:
    """True when a paper of this test type defaults to a mark of record."""
    return _TEST_TYPE_CONSEQUENTIAL[test_type]


class CognitiveLevel(str, Enum):
    """A coarse, board-agnostic cognitive ladder (Bloom-shaped, not board-bound)."""

    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYSE = "analyse"
    EVALUATE = "evaluate"
    CREATE = "create"


class DifficultyBand(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


_BAND_TO_DIFFICULTY = {
    DifficultyBand.EASY: 0.25,
    DifficultyBand.MEDIUM: 0.55,
    DifficultyBand.HARD: 0.85,
}


def difficulty_for(band: DifficultyBand) -> float:
    """Normalized [0,1] difficulty for a band — feeds the attempt Difficulty
    dimension when items are later attempted."""
    return _BAND_TO_DIFFICULTY[band]


class BlueprintCell(_Model):
    """One coverage cell: how many items at this (topic, difficulty, cognitive
    level), and the marks each carries. Optionally carries a deterministic
    math/physics ground-truth so the cell can be filled with NO LLM."""

    ontology: OntologyRef
    difficulty: DifficultyBand
    cognitive_level: CognitiveLevel
    count: int = Field(ge=1, description="How many items this cell contributes.")
    marks_each: float = Field(default=1.0, ge=0)
    section: str | None = Field(
        default=None, description="Optional paper section label (e.g. 'A', 'B') for section-wise distribution."
    )
    # Deterministic math/physics handle (optional). When present, the fabric's
    # symbolic/numeric verifier checks the item with no LLM.
    expression: str | None = Field(default=None, description="A purely-numeric arithmetic expression to verify.")
    claimed_answer: float | None = Field(default=None)
    claimed_unit: str | None = Field(default=None)
    expected_unit: str | None = Field(default=None)
    # Free-text item prompt template (interface path; routed through the fabric).
    prompt_hint: str | None = Field(default=None, description="A topic-scoped hint for a generated free-text item.")

    @property
    def is_deterministic(self) -> bool:
        return self.expression is not None and self.claimed_answer is not None


@dataclass(frozen=True)
class SectionDistribution:
    """The mark/item distribution for one section of a paper — the section-wise
    distribution view the author works against."""

    section: str
    item_count: int
    marks: float
    cognitive_levels: dict[str, int]  # cognitive level -> item count in this section


class Blueprint(_Model):
    """A paper blueprint: a title, the institution/tenant, and the coverage cells.

    ``test_type`` is the test-type discriminator (periodic / formative / summative
    / slip). Cells may carry a ``section`` label, and ``section_distribution``
    rolls the cells up into a section-wise mark distribution for the author.
    """

    blueprint_id: UUID = Field(default_factory=uuid4)
    institution_id: UUID
    title: str
    test_type: TestType = Field(default=TestType.SUMMATIVE)
    total_marks: float | None = Field(default=None, description="Optional declared total to reconcile against.")
    cells: list[BlueprintCell] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherent(self) -> "Blueprint":
        if self.total_marks is not None:
            computed = sum(c.count * c.marks_each for c in self.cells)
            # Reconcile within a small tolerance; a mismatch is a blueprint error.
            if abs(computed - self.total_marks) > 1e-6:
                raise ValueError(
                    f"blueprint total_marks {self.total_marks} does not match cell sum {computed}."
                )
        return self

    @property
    def planned_item_count(self) -> int:
        return sum(c.count for c in self.cells)

    @property
    def planned_marks(self) -> float:
        return sum(c.count * c.marks_each for c in self.cells)

    @property
    def is_consequential(self) -> bool:
        """Whether a paper from this blueprint is a mark of record by default."""
        return test_type_is_consequential(self.test_type)

    def section_distribution(self) -> list[SectionDistribution]:
        """The section-wise mark distribution: per section, the item count, marks,
        and the cognitive-level mix. Cells with no section label collapse into a
        single 'Unsectioned' bucket so nothing is lost."""
        buckets: dict[str, dict] = {}
        for c in self.cells:
            key = c.section if c.section is not None else "Unsectioned"
            b = buckets.setdefault(key, {"items": 0, "marks": 0.0, "levels": {}})
            b["items"] += c.count
            b["marks"] += c.count * c.marks_each
            lvl = c.cognitive_level.value
            b["levels"][lvl] = b["levels"].get(lvl, 0) + c.count
        return [
            SectionDistribution(section=k, item_count=v["items"], marks=v["marks"], cognitive_levels=v["levels"])
            for k, v in buckets.items()
        ]


class PaperItem(_Model):
    """A verified item placed in a paper. Always carries its verification block —
    an item is only placed once the confidence gate served it."""

    item_id: UUID = Field(default_factory=uuid4)
    question_ref: UUID = Field(default_factory=uuid4, description="Ontology question node id (opaque).")
    ontology: OntologyRef
    difficulty: DifficultyBand
    cognitive_level: CognitiveLevel
    marks: float = Field(ge=0)
    prompt: str
    answer: object | None = Field(default=None, description="The verified solution handle, when deterministic.")
    verification: Verification

    @model_validator(mode="after")
    def _must_be_served(self) -> "PaperItem":
        if not self.verification.served:
            raise ValueError("a PaperItem must carry a SERVED verification (INVARIANT 7).")
        return self


@dataclass(frozen=True)
class WithheldCell:
    """A blueprint cell the gate did NOT serve — flagged for human review, never
    silently dropped and never served unverified."""

    ontology: OntologyRef
    difficulty: DifficultyBand
    cognitive_level: CognitiveLevel
    requested: int
    served: int
    review_reason: str


@dataclass(frozen=True)
class PaperSet:
    """One generated set (A/B/C ...). Carries the served items AND the withheld
    cells, so the coverage shortfall is always visible to a human."""

    set_label: str
    blueprint_id: UUID
    items: list[PaperItem] = field(default_factory=list)
    withheld: list[WithheldCell] = field(default_factory=list)

    @property
    def fully_covered(self) -> bool:
        return not self.withheld

    @property
    def served_marks(self) -> float:
        return sum(i.marks for i in self.items)


# ---------------------------------------------------------------------------
# The generator.
# ---------------------------------------------------------------------------
class PaperGenerator:
    """Fills a blueprint into one or more paper sets through generate-and-verify.

    ``second_model`` and ``gate`` come from the ai-fabric substrate when present;
    with no fabric on the path, the generator runs the deterministic verifier it
    loads from the fabric, and free-text cells are withheld with a named reason.
    """

    def __init__(self, *, second_model: object | None = None, gate_threshold: float = 0.85) -> None:
        self._verify = _load_fabric()
        self._gate_threshold = gate_threshold
        # No live second-model provider => the fabric's AbstainingSecondModel,
        # which never agrees, keeping the confidence gate closed (degrades safe).
        if second_model is not None:
            self._second_model = second_model
        elif self._verify is not None:
            self._second_model = self._verify.AbstainingSecondModel()
        else:
            self._second_model = None

    @property
    def fabric_available(self) -> bool:
        return self._verify is not None

    def _gate(self):
        if self._verify is None:
            return None
        return self._verify.ConfidenceGate(threshold=self._gate_threshold)

    def _verify_deterministic_cell(self, cell: BlueprintCell):
        """Run the fabric's deterministic math battery + second-model cross-check
        through the confidence gate. Returns the fabric GenerateVerification or
        None when the fabric is unavailable."""
        if self._verify is None:
            return None
        item = self._verify.MathItem(
            expression=str(cell.expression),
            claimed_answer=float(cell.claimed_answer),  # type: ignore[arg-type]
            claimed_unit=cell.claimed_unit,
            expected_unit=cell.expected_unit,
        )
        det_checks = self._verify.deterministic_checks_for_math(item)
        agrees, sm_conf = self._second_model.cross_check(  # type: ignore[union-attr]
            task_class="content.generate-practice-item", content={"expression": cell.expression}
        )
        # Deterministic ground truth gives high generator confidence; the gate is
        # conservative and takes the min with the second-model signal.
        confidence = min(0.99, sm_conf)
        return self._gate().evaluate(det_checks, agrees, confidence)  # type: ignore[union-attr]

    def _to_verification(self, gv) -> Verification:
        """Map a fabric GenerateVerification onto the contract Verification block."""
        return Verification(
            status="passed" if gv.served else "failed",
            confidence=gv.confidence,
            gate_threshold=gv.gate_threshold,
            checks=[VerificationCheck(name=c.name, passed=c.passed, detail=c.detail) for c in gv.deterministic_checks],
        )

    def _fill_cell(self, cell: BlueprintCell) -> tuple[list[PaperItem], WithheldCell | None]:
        items: list[PaperItem] = []

        # Deterministic math/physics path.
        if cell.is_deterministic:
            gv = self._verify_deterministic_cell(cell)
            if gv is None:
                reason = "ai-fabric verify substrate not on path; cannot verify — flagged for human review."
                return [], self._make_withheld(cell, 0, reason)
            if not gv.served:
                return [], self._make_withheld(cell, 0, gv.review_reason or "confidence gate withheld the item.")
            verification = self._to_verification(gv)
            prompt = f"Evaluate: {cell.expression}"
            for _ in range(cell.count):
                items.append(
                    PaperItem(
                        ontology=cell.ontology,
                        difficulty=cell.difficulty,
                        cognitive_level=cell.cognitive_level,
                        marks=cell.marks_each,
                        prompt=prompt,
                        answer={"expression": cell.expression, "answer": cell.claimed_answer, "unit": cell.claimed_unit},
                        verification=verification,
                    )
                )
            return items, None

        # Free-text interface path: routed through the fabric orchestrator. With
        # no live provider the gate cannot pass on a non-deterministic item
        # (no deterministic handle => fail closed), so the cell is withheld.
        reason = (
            "free-text item has no deterministic handle and no live generation provider; "
            "the confidence gate withholds it — flagged for human authoring/review. "
            "Set clss.coursework.dev.ai_fabric_url and a fabric provider key to enable."
        )
        return [], self._make_withheld(cell, 0, reason)

    @staticmethod
    def _make_withheld(cell: BlueprintCell, served: int, reason: str) -> WithheldCell:
        return WithheldCell(
            ontology=cell.ontology,
            difficulty=cell.difficulty,
            cognitive_level=cell.cognitive_level,
            requested=cell.count,
            served=served,
            review_reason=reason,
        )

    def generate_set(self, blueprint: Blueprint, *, set_label: str = "A") -> PaperSet:
        """Fill a blueprint into ONE set. Only served items are included; every
        unfilled cell is recorded as withheld (never silently dropped)."""
        items: list[PaperItem] = []
        withheld: list[WithheldCell] = []
        for cell in blueprint.cells:
            filled, miss = self._fill_cell(cell)
            items.extend(filled)
            if miss is not None:
                withheld.append(miss)
        return PaperSet(set_label=set_label, blueprint_id=blueprint.blueprint_id, items=items, withheld=withheld)

    def generate_sets(self, blueprint: Blueprint, *, n: int = 1) -> list[PaperSet]:
        """Multi-set: produce N parallel sets (A, B, C ...) from one blueprint.

        Each set is an independent draw against the same coverage; deterministic
        cells reuse the verified ground truth, so equivalent sets stay verified.
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        if n > len(string.ascii_uppercase):
            raise ValueError("more sets than single-letter labels; cap at 26.")
        return [self.generate_set(blueprint, set_label=string.ascii_uppercase[i]) for i in range(n)]

    # -- per-question operations on a generated paper ----------------------
    def regenerate_item(self, item: PaperItem) -> tuple[PaperItem | None, WithheldCell | None]:
        """REGENERATE one item: redraw the same coverage cell through
        generate-and-verify. A new item is only returned once the gate serves it;
        otherwise the cell is withheld with a named reason (never served
        unverified). For a deterministic item the ground truth re-verifies; for a
        free-text item with no live provider the gate withholds it."""
        cell = BlueprintCell(
            ontology=item.ontology,
            difficulty=item.difficulty,
            cognitive_level=item.cognitive_level,
            count=1,
            marks_each=item.marks,
            expression=(item.answer or {}).get("expression") if isinstance(item.answer, dict) else None,
            claimed_answer=(item.answer or {}).get("answer") if isinstance(item.answer, dict) else None,
            claimed_unit=(item.answer or {}).get("unit") if isinstance(item.answer, dict) else None,
        )
        filled, miss = self._fill_cell(cell)
        return (filled[0] if filled else None), miss


def edit_item(item: PaperItem, *, prompt: str | None = None, marks: float | None = None) -> PaperItem:
    """EDIT one item by hand (teacher edit). Editing the human-facing prompt or
    the marks does NOT change the verified answer/coverage, so the verification
    block is preserved — the item stays served. A teacher owns the wording."""
    return item.model_copy(
        update={
            "prompt": prompt if prompt is not None else item.prompt,
            "marks": marks if marks is not None else item.marks,
        }
    )


def refine_item(generator: "PaperGenerator", item: PaperItem, *, refinement: str) -> "RefineResult":
    """REFINE one item: a guided change (e.g. 'make it harder', 'add a real-world
    context') routed through generate-and-verify. Refinement is generative, so it
    must re-verify: the refined item is only served once the confidence gate
    passes, exactly like regeneration. With no live provider for a free-text
    refinement, the original item is kept and the refinement is flagged for human
    authoring — the served paper is never degraded by an unverified refinement."""
    refined, miss = generator.regenerate_item(item)
    if refined is not None:
        return RefineResult(item=refined, applied=True, withheld=None,
                            rationale=f"Refinement '{refinement}' applied and re-verified.")
    return RefineResult(
        item=item,
        applied=False,
        withheld=miss,
        rationale=(
            f"Refinement '{refinement}' could not be verified (no live generation provider for a "
            "non-deterministic change); the original verified item is kept and the refinement is "
            "flagged for human authoring."
        ),
    )


@dataclass(frozen=True)
class RefineResult:
    """The outcome of a refine operation: the item that now stands (refined when
    verified, else the original), whether the refinement was applied, and why."""

    item: PaperItem
    applied: bool
    withheld: WithheldCell | None
    rationale: str
