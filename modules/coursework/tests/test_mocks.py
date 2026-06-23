"""Blueprint-aligned mock-test generation.

A mock is a paper drawn against the SAME blueprint a real exam uses, so its
coverage (topic x difficulty band x cognitive level) and mark distribution match
the real thing — and it can be generated in multiple parallel sets. A mock is
NON-CONSEQUENTIAL practice: it never yields a mark of record, and it is held to
the same generate-and-verify bar as a real paper (withheld cells are surfaced,
never silently dropped).
"""

from __future__ import annotations

from uuid import uuid4

from app.assignments import OntologyRef
from app.mocks import MockTestGenerator
from app.papers import Blueprint, BlueprintCell, CognitiveLevel, DifficultyBand


class _AgreeingSecondModel:
    """A live second model that agrees — lets the confidence gate serve verified
    deterministic items (no network)."""

    def cross_check(self, *, task_class, content):
        return (True, 0.97)


def _ont() -> OntologyRef:
    return OntologyRef(topic_id=uuid4())


def _multicell_blueprint() -> Blueprint:
    """A blueprint spanning multiple topic x difficulty x cognitive-level cells,
    every cell deterministic so it can be served with an agreeing second model."""
    return Blueprint(
        institution_id=uuid4(),
        title="Mid-term mock",
        cells=[
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.EASY,
                cognitive_level=CognitiveLevel.REMEMBER,
                count=2,
                marks_each=1.0,
                expression="3+4",
                claimed_answer=7.0,
            ),
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.MEDIUM,
                cognitive_level=CognitiveLevel.APPLY,
                count=3,
                marks_each=2.0,
                expression="6*7",
                claimed_answer=42.0,
            ),
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.HARD,
                cognitive_level=CognitiveLevel.ANALYSE,
                count=1,
                marks_each=5.0,
                expression="100-1",
                claimed_answer=99.0,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Alignment to a blueprint.
# ---------------------------------------------------------------------------
def test_mock_is_non_consequential_practice():
    gen = MockTestGenerator(second_model=_AgreeingSecondModel())
    mock = gen.generate_mock(_multicell_blueprint())
    # A mock is never a mark of record.
    assert mock.consequential is False


def test_mock_fully_aligns_to_blueprint_when_served():
    bp = _multicell_blueprint()
    gen = MockTestGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    mock = gen.generate_mock(bp)
    cov = mock.coverage
    # Item count + marks mirror the blueprint exactly.
    assert cov.planned_item_count == bp.planned_item_count == 6
    assert cov.served_item_count == 6
    assert cov.planned_marks == bp.planned_marks
    assert cov.served_marks == bp.planned_marks
    assert cov.withheld_cell_count == 0
    assert cov.aligned is True
    assert mock.fully_aligned is True
    assert cov.coverage_ratio == 1.0


def test_mock_coverage_spans_every_topic_difficulty_cognitive_cell():
    """The served items reproduce the blueprint's (difficulty x cognitive-level)
    coverage grid — alignment is by coverage, not just totals."""
    bp = _multicell_blueprint()
    gen = MockTestGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    mock = gen.generate_mock(bp)

    planned = {
        (c.difficulty, c.cognitive_level): c.count for c in bp.cells
    }
    served: dict[tuple, int] = {}
    for item in mock.paper_set.items:
        key = (item.difficulty, item.cognitive_level)
        served[key] = served.get(key, 0) + 1
    assert served == planned


def test_mock_marks_distribution_matches_blueprint_per_band():
    """Mark distribution across difficulty bands mirrors the blueprint, so the
    mock 'feels' like the real exam, not just shares a total."""
    bp = _multicell_blueprint()
    gen = MockTestGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    mock = gen.generate_mock(bp)

    planned_marks = {
        c.difficulty: 0.0 for c in bp.cells
    }
    for c in bp.cells:
        planned_marks[c.difficulty] += c.count * c.marks_each
    served_marks: dict = {b: 0.0 for b in planned_marks}
    for item in mock.paper_set.items:
        served_marks[item.difficulty] += item.marks
    assert served_marks == planned_marks


# ---------------------------------------------------------------------------
# Multi-set.
# ---------------------------------------------------------------------------
def test_multi_set_mock_series_parallel_sets():
    bp = _multicell_blueprint()
    gen = MockTestGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    series = gen.generate_mock_series(bp, n=3)
    assert [m.set_label for m in series] == ["A", "B", "C"]
    # Every set draws against the SAME blueprint coverage.
    for m in series:
        assert m.blueprint_id == bp.blueprint_id
        assert m.coverage.served_item_count == bp.planned_item_count
        assert m.fully_aligned is True
        assert m.consequential is False


# ---------------------------------------------------------------------------
# Graceful degradation — withheld content surfaced, never silently dropped.
# ---------------------------------------------------------------------------
def test_mock_partially_aligned_surfaces_withheld_cells():
    """A free-text cell has no deterministic handle; with no live provider the gate
    withholds it. The mock must report a coverage SHORTFALL, never hide it."""
    bp = Blueprint(
        institution_id=uuid4(),
        title="mixed mock",
        cells=[
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.EASY,
                cognitive_level=CognitiveLevel.APPLY,
                count=2,
                marks_each=1.0,
                expression="2*2",
                claimed_answer=4.0,
            ),
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.MEDIUM,
                cognitive_level=CognitiveLevel.EVALUATE,
                count=1,
                marks_each=4.0,
                prompt_hint="Discuss the causes of soil erosion.",
            ),
        ],
    )
    gen = MockTestGenerator(second_model=_AgreeingSecondModel())
    mock = gen.generate_mock(bp)
    cov = mock.coverage
    # The free-text cell is always withheld (no provider), so the mock is never
    # fully aligned and says so by name.
    assert cov.withheld_cell_count >= 1
    assert cov.aligned is False
    assert mock.fully_aligned is False
    assert cov.served_item_count < cov.planned_item_count
    assert 0.0 <= cov.coverage_ratio < 1.0
    assert "withheld" in cov.rationale.lower()


def test_mock_with_no_fabric_degrades_to_full_shortfall():
    """With no fabric/second model the deterministic cell cannot be served; the
    mock reports the shortfall and never serves unverified content."""
    gen = MockTestGenerator()  # no second model -> gate closed / fabric may be absent
    mock = gen.generate_mock(_multicell_blueprint())
    cov = mock.coverage
    if gen.fabric_available:
        # Fabric present but no agreeing second model -> everything withheld.
        assert cov.served_item_count == 0
        assert cov.withheld_cell_count == len(_multicell_blueprint().cells)
    # In every degraded case the mock is honest about not being aligned.
    assert cov.aligned is False
    assert mock.consequential is False


def test_empty_mock_never_falsely_claims_alignment():
    gen = MockTestGenerator()
    mock = gen.generate_mock(_multicell_blueprint())
    cov = mock.coverage
    if cov.served_item_count == 0:
        assert cov.coverage_ratio == 0.0
        assert cov.aligned is False
