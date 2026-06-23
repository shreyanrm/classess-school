"""Test-type discriminator, section-wise distribution, coverage view, and
per-question edit / regenerate / refine operations."""

from __future__ import annotations

from uuid import uuid4

from app.assignments import OntologyRef
from app.coverage import TopicCoverageStatus, compute_coverage
from app.papers import (
    Blueprint,
    BlueprintCell,
    CognitiveLevel,
    DifficultyBand,
    PaperGenerator,
    TestType,
    edit_item,
    refine_item,
)
from app.papers import test_type_is_consequential as _is_consequential


def _ont(topic_id=None) -> OntologyRef:
    return OntologyRef(topic_id=topic_id or uuid4())


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.97)


def _sectioned_blueprint(topic_a=None, topic_b=None) -> Blueprint:
    return Blueprint(
        institution_id=uuid4(),
        title="Unit test",
        test_type=TestType.PERIODIC,
        cells=[
            BlueprintCell(
                ontology=_ont(topic_a),
                difficulty=DifficultyBand.EASY,
                cognitive_level=CognitiveLevel.REMEMBER,
                count=3,
                marks_each=1.0,
                section="A",
            ),
            BlueprintCell(
                ontology=_ont(topic_b),
                difficulty=DifficultyBand.HARD,
                cognitive_level=CognitiveLevel.ANALYSE,
                count=2,
                marks_each=5.0,
                section="B",
            ),
        ],
    )


def test_consequential_mapping_by_test_type():
    assert _is_consequential(TestType.SUMMATIVE) is True
    assert _is_consequential(TestType.PERIODIC) is True
    assert _is_consequential(TestType.FORMATIVE) is False
    assert _is_consequential(TestType.SLIP) is False


def test_blueprint_test_type_drives_consequential():
    bp = _sectioned_blueprint()
    assert bp.test_type is TestType.PERIODIC
    assert bp.is_consequential is True
    slip = Blueprint(
        institution_id=uuid4(),
        title="exit ticket",
        test_type=TestType.SLIP,
        cells=[BlueprintCell(ontology=_ont(), difficulty=DifficultyBand.EASY, cognitive_level=CognitiveLevel.REMEMBER, count=1)],
    )
    assert slip.is_consequential is False


def test_section_wise_distribution():
    bp = _sectioned_blueprint()
    dist = {sd.section: sd for sd in bp.section_distribution()}
    assert dist["A"].item_count == 3
    assert dist["A"].marks == 3.0
    assert dist["B"].marks == 10.0
    assert dist["B"].cognitive_levels == {"analyse": 2}


def test_coverage_view_classifies_topics():
    topic_a, topic_b = uuid4(), uuid4()
    bp = _sectioned_blueprint(topic_a=topic_a, topic_b=topic_b)
    # A taught (and not examined), B not taught.
    view = compute_coverage(
        bp,
        taught_topic_ids={topic_a},
        previously_examined_topic_ids=set(),
    )
    assert topic_a in view.of_status(TopicCoverageStatus.COMPLETED)
    assert topic_b in view.of_status(TopicCoverageStatus.UNTAUGHT)
    assert view.testing_untaught is True


def test_coverage_view_previously_examined_and_gaps():
    topic_a, topic_b, other = uuid4(), uuid4(), uuid4()
    bp = _sectioned_blueprint(topic_a=topic_a, topic_b=topic_b)
    view = compute_coverage(
        bp,
        taught_topic_ids={topic_a, topic_b},
        previously_examined_topic_ids={topic_a},
        curriculum_topic_ids={topic_a, topic_b, other},
    )
    assert topic_a in view.of_status(TopicCoverageStatus.PREVIOUSLY_EXAMINED)
    assert topic_b in view.of_status(TopicCoverageStatus.COMPLETED)
    assert other in view.of_status(TopicCoverageStatus.NOT_IN_BLUEPRINT)
    assert view.testing_untaught is False
    assert view.counts["previously_examined"] == 1


def _math_blueprint() -> Blueprint:
    return Blueprint(
        institution_id=uuid4(),
        title="arith",
        cells=[
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.EASY,
                cognitive_level=CognitiveLevel.APPLY,
                count=1,
                marks_each=2.0,
                expression="6*7",
                claimed_answer=42.0,
            )
        ],
    )


def test_edit_item_preserves_verification():
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    paper = gen.generate_set(_math_blueprint())
    item = paper.items[0]
    edited = edit_item(item, prompt="Compute six times seven.", marks=3.0)
    assert edited.prompt == "Compute six times seven."
    assert edited.marks == 3.0
    assert edited.verification.served is True  # editing wording keeps it served


def test_regenerate_deterministic_item_reverifies():
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    paper = gen.generate_set(_math_blueprint())
    new_item, miss = gen.regenerate_item(paper.items[0])
    assert miss is None
    assert new_item is not None
    assert new_item.verification.served is True


def test_refine_free_text_keeps_original_and_flags():
    # A free-text refinement with no provider cannot verify; the original verified
    # item is kept and the refinement is flagged (never serves unverified).
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        import pytest

        pytest.skip("ai-fabric verify substrate not on path")
    paper = gen.generate_set(_math_blueprint())
    item = paper.items[0]
    # Strip the deterministic answer so refine has no handle to re-verify.
    free_like = item.model_copy(update={"answer": None})
    result = refine_item(gen, free_like, refinement="make it harder")
    assert result.applied is False
    assert result.item is free_like  # original kept
    assert result.withheld is not None
