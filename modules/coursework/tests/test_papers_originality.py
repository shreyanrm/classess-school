"""Blueprint paper generation (generate-and-verify) + originality interface."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.assignments import OntologyRef
from app.originality import (
    OriginalitySignal,
    check_originality,
)
from app.papers import (
    Blueprint,
    BlueprintCell,
    CognitiveLevel,
    DifficultyBand,
    PaperGenerator,
    difficulty_for,
)


def _ont() -> OntologyRef:
    return OntologyRef(topic_id=uuid4())


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.97)


def _math_blueprint(count: int = 2) -> Blueprint:
    return Blueprint(
        institution_id=uuid4(),
        title="Arithmetic check",
        cells=[
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.EASY,
                cognitive_level=CognitiveLevel.APPLY,
                count=count,
                marks_each=1.0,
                expression="7*8",
                claimed_answer=56.0,
            )
        ],
    )


def test_blueprint_marks_reconciliation():
    with pytest.raises(Exception):
        Blueprint(
            institution_id=uuid4(),
            title="bad total",
            total_marks=99.0,
            cells=[
                BlueprintCell(
                    ontology=_ont(),
                    difficulty=DifficultyBand.EASY,
                    cognitive_level=CognitiveLevel.REMEMBER,
                    count=1,
                    marks_each=1.0,
                )
            ],
        )


def test_deterministic_cell_withheld_without_second_model():
    # No second model => the confidence gate stays closed; the cell is WITHHELD,
    # never served unverified.
    gen = PaperGenerator()
    if not gen.fabric_available:
        pytest.skip("ai-fabric verify substrate not on path")
    paper = gen.generate_set(_math_blueprint())
    assert paper.items == []
    assert len(paper.withheld) == 1
    assert paper.fully_covered is False


def test_deterministic_cell_served_with_agreeing_second_model():
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        pytest.skip("ai-fabric verify substrate not on path")
    paper = gen.generate_set(_math_blueprint(count=3))
    assert len(paper.items) == 3
    assert paper.fully_covered is True
    for item in paper.items:
        assert item.verification.served is True
        assert item.marks == 1.0


def test_wrong_claimed_answer_is_withheld():
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        pytest.skip("ai-fabric verify substrate not on path")
    bad = Blueprint(
        institution_id=uuid4(),
        title="bad item",
        cells=[
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.EASY,
                cognitive_level=CognitiveLevel.APPLY,
                count=1,
                expression="7*8",
                claimed_answer=55.0,  # wrong; deterministic check fails
            )
        ],
    )
    paper = gen.generate_set(bad)
    assert paper.items == []
    assert paper.withheld[0].served == 0


def test_free_text_cell_is_withheld_without_provider():
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    bp = Blueprint(
        institution_id=uuid4(),
        title="free text",
        cells=[
            BlueprintCell(
                ontology=_ont(),
                difficulty=DifficultyBand.MEDIUM,
                cognitive_level=CognitiveLevel.ANALYSE,
                count=1,
                prompt_hint="Explain why the sky is blue.",
            )
        ],
    )
    paper = gen.generate_set(bp)
    assert paper.items == []
    assert len(paper.withheld) == 1


def test_multi_set_generation():
    gen = PaperGenerator(second_model=_AgreeingSecondModel())
    if not gen.fabric_available:
        pytest.skip("ai-fabric verify substrate not on path")
    sets = gen.generate_sets(_math_blueprint(count=2), n=3)
    assert [s.set_label for s in sets] == ["A", "B", "C"]
    for s in sets:
        assert len(s.items) == 2


def test_difficulty_band_mapping():
    assert difficulty_for(DifficultyBand.EASY) < difficulty_for(DifficultyBand.HARD)


def test_originality_undetermined_without_corpus_or_provider():
    res = check_originality(submission_ref=uuid4(), text="some answer")
    assert res.signal is OriginalitySignal.UNDETERMINED
    assert res.needs_human_review is False


def test_originality_flags_high_similarity_for_review():
    text = "the quick brown fox jumps over the lazy dog every single morning"
    corpus = {"other-submission": text}  # identical
    res = check_originality(submission_ref=uuid4(), text=text, corpus=corpus)
    assert res.signal is OriginalitySignal.NEEDS_REVIEW
    assert res.needs_human_review is True
    assert res.max_similarity >= 0.65
    # It is a recommendation to a human — never an automatic accusation.
    assert res.rung == "recommend"


def test_originality_distinct_text_likely_original():
    res = check_originality(
        submission_ref=uuid4(),
        text="photosynthesis converts light energy into chemical energy",
        corpus={"other": "the mitochondria produces atp through cellular respiration"},
    )
    assert res.signal is OriginalitySignal.LIKELY_ORIGINAL
    assert res.needs_human_review is False
