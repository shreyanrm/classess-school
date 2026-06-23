"""Blueprint-aligned mock-test generation (B6, domain 13).

The dossier: "mocks mirror the real format and difficulty" — "exam-specific mock
tests aligned to the school's blueprint". A mock test is a paper drawn against
the SAME blueprint a real exam uses, so its coverage (topic x difficulty band x
cognitive level) and mark distribution match the real thing, in multiple parallel
sets so a learner can sit several realistic attempts.

This module is a thin, honest layer over ``papers``: it REUSES ``PaperGenerator``
and the ``Blueprint`` — it does not re-implement generation, and it does not relax
generate-and-verify (INVARIANT 7). Every item in a mock carries a SERVED
verification, exactly like a real paper; withheld cells are surfaced, never
silently dropped. With no live second-model/provider the generator degrades
safely and the mock reports its coverage shortfall.

A mock is explicitly NON-CONSEQUENTIAL practice: it never produces a mark of
record. Readiness forecasting (the predictive projection) is the intelligence
layer's job and is NOT done here — this module only states, plainly, how well a
mock covered its blueprint, so a forecasting layer can consume that.

Pure composition over ``papers``. Import-safe; no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from .papers import Blueprint, PaperGenerator, PaperSet


@dataclass(frozen=True)
class MockCoverage:
    """How faithfully a mock set matched its blueprint — the alignment evidence.

    A mock is "aligned" when it covers the full blueprint (no withheld cells) and
    its served marks match the blueprint's planned marks. When content is withheld
    (e.g. no live provider for free-text cells), the mock is partially aligned and
    says so by name — never a silent shortfall.
    """

    planned_item_count: int
    served_item_count: int
    planned_marks: float
    served_marks: float
    withheld_cell_count: int
    aligned: bool
    rationale: str

    @property
    def coverage_ratio(self) -> float:
        """Served items as a fraction of planned items, in [0,1]."""
        if self.planned_item_count <= 0:
            return 0.0
        return self.served_item_count / self.planned_item_count


@dataclass(frozen=True)
class MockTest:
    """One generated mock set, paired with its blueprint-alignment coverage. A
    mock is NON-CONSEQUENTIAL practice — it never yields a mark of record."""

    blueprint_id: UUID
    paper_set: PaperSet
    coverage: MockCoverage
    consequential: bool = False  # a mock is practice; never a mark of record

    @property
    def set_label(self) -> str:
        return self.paper_set.set_label

    @property
    def fully_aligned(self) -> bool:
        return self.coverage.aligned


def _coverage_for(blueprint: Blueprint, paper: PaperSet) -> MockCoverage:
    planned_items = blueprint.planned_item_count
    served_items = len(paper.items)
    planned_marks = blueprint.planned_marks
    served_marks = paper.served_marks
    withheld = len(paper.withheld)

    marks_match = abs(planned_marks - served_marks) <= 1e-6
    aligned = withheld == 0 and served_items == planned_items and marks_match

    if aligned:
        rationale = (
            f"Mock mirrors the blueprint: {served_items}/{planned_items} items and "
            f"{served_marks:g}/{planned_marks:g} marks across the same topic x "
            "difficulty x cognitive-level coverage."
        )
    else:
        rationale = (
            f"Mock partially aligned: {served_items}/{planned_items} items, "
            f"{served_marks:g}/{planned_marks:g} marks, {withheld} blueprint cell(s) "
            "withheld (unverified content is never served — flagged for human "
            "authoring/review). Enable a generation provider to close the gap."
        )

    return MockCoverage(
        planned_item_count=planned_items,
        served_item_count=served_items,
        planned_marks=planned_marks,
        served_marks=served_marks,
        withheld_cell_count=withheld,
        aligned=aligned,
        rationale=rationale,
    )


class MockTestGenerator:
    """Generates blueprint-aligned mock tests by reusing ``PaperGenerator``.

    ``second_model`` and ``gate_threshold`` are passed straight through to the
    underlying paper generator, so a mock is held to the SAME generate-and-verify
    bar as a real exam paper — no relaxed path for "just practice".
    """

    def __init__(self, *, second_model: object | None = None, gate_threshold: float = 0.85) -> None:
        self._generator = PaperGenerator(second_model=second_model, gate_threshold=gate_threshold)

    @property
    def fabric_available(self) -> bool:
        return self._generator.fabric_available

    def generate_mock(self, blueprint: Blueprint, *, set_label: str = "A") -> MockTest:
        """Generate ONE mock set aligned to ``blueprint``."""
        paper = self._generator.generate_set(blueprint, set_label=set_label)
        return MockTest(
            blueprint_id=blueprint.blueprint_id,
            paper_set=paper,
            coverage=_coverage_for(blueprint, paper),
        )

    def generate_mock_series(self, blueprint: Blueprint, *, n: int = 1) -> list[MockTest]:
        """Multi-set: generate N parallel mock sets (A/B/C ...) from one blueprint.

        Each set is an independent draw against the SAME blueprint coverage, so a
        learner can sit several equivalent-but-distinct mocks. Each mock carries
        its own alignment coverage.
        """
        sets = self._generator.generate_sets(blueprint, n=n)
        return [
            MockTest(
                blueprint_id=blueprint.blueprint_id,
                paper_set=paper,
                coverage=_coverage_for(blueprint, paper),
            )
            for paper in sets
        ]
