"""Worksheet generation: every item rides the per-item confidence gate.

A worksheet is exactly the set of items that INDIVIDUALLY passed the gate
(INVARIANT 7). Nothing unverified is served; withheld items are reported, never
fabricated. The provider is mocked via the spine's injectable second model.
"""

import content  # noqa: F401 — ensures the spine path is bootstrapped
from content.generate import (
    ContentGenerator,
    MaterialKind,
    MaterialRequest,
)


class _AgreeingSecondModel:
    """Provider-mock stand-in: an independent second model that agrees, so the
    deterministic-correct items clear the gate (the live cross-check provider is
    not present in CI)."""

    def cross_check(self, *, task_class, content):
        return (True, 0.99)


def _orch_with_agreeing_model():
    from app.orchestrator import Orchestrator  # spine, via _spine bootstrap

    return Orchestrator(second_model=_AgreeingSecondModel())


def test_worksheet_serves_only_gate_passing_items_with_answer_key():
    """Mixed item types: two deterministically-correct items pass the gate and a
    wrong item is WITHHELD. The worksheet carries an answer key for served items
    only."""
    gen = ContentGenerator(orchestrator=_orch_with_agreeing_model())
    ws = gen.generate_worksheet(
        topic_id="topic-1",
        item_requests=[
            MaterialRequest(topic_id="x", kind=MaterialKind.PRACTICE_ITEM,
                            payload={"expression": "6 * 7", "claimed_answer": 42.0}),
            MaterialRequest(topic_id="x", kind=MaterialKind.LESSON_VISUAL,
                            payload={"expression": "x ** 2", "samples": [[2, 4], [3, 9]]}),
            MaterialRequest(topic_id="x", kind=MaterialKind.PRACTICE_ITEM,
                            payload={"expression": "6 * 7", "claimed_answer": 41.0}),  # wrong
        ],
        outcome_ids=("o1", "o2"),
    )
    assert ws.served is True
    assert len(ws.items) == 2            # the two verified items
    assert len(ws.withheld) == 1         # the wrong item, withheld by the gate
    assert ws.withheld[0][0] == 2        # index of the withheld item
    # Answer key covers exactly the served items.
    assert dict(ws.answer_key)[0] == 42.0
    # The worksheet forced its own topic onto every item (coherent answer key).
    assert ws.topic_id == "topic-1"
    assert ws.outcome_ids == ("o1", "o2")


def test_worksheet_withholds_everything_with_abstaining_second_model():
    """The DEFAULT (no provider, abstaining second model) holds the gate on every
    item — proving the confidence gate is honoured, never bypassed. Nothing is
    served and the worksheet is not served."""
    gen = ContentGenerator()  # abstaining second model by default
    ws = gen.generate_worksheet(
        topic_id="topic-1",
        item_requests=[
            MaterialRequest(topic_id="topic-1", kind=MaterialKind.PRACTICE_ITEM,
                            payload={"expression": "6 * 7", "claimed_answer": 42.0}),
        ],
    )
    assert ws.served is False
    assert ws.items == ()
    assert len(ws.withheld) == 1


def test_worksheet_never_fabricates_narrative_items_without_provider():
    """A narrative (explanation) item has no deterministic oracle and no live
    provider => withheld, never a fabricated explanation."""
    gen = ContentGenerator()
    ws = gen.generate_worksheet(
        topic_id="topic-1",
        item_requests=[
            MaterialRequest(topic_id="topic-1", kind=MaterialKind.EXPLANATION,
                            payload={"prompt": "explain HCF"}),
        ],
    )
    assert ws.served is False
    assert len(ws.withheld) == 1
