"""Generate: nothing unverified is served; deterministic math path is real."""

import content
from content.generate import (
    ContentGenerator,
    MaterialKind,
    MaterialRequest,
)
from content.repository import ApprovalState, InMemoryContentRepository


def test_deterministic_math_item_is_verified_and_served():
    """A math item with a correct expression + claimed answer passes the spine's
    real deterministic verifier. The second model still abstains by default, so
    the gate withholds — proving the gate is honoured, not bypassed."""
    gen = ContentGenerator()
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
    )
    outcome = gen.generate(req)
    # With the abstaining second model, the gate withholds — never served blind.
    assert outcome.served is False
    assert outcome.material is None
    assert outcome.review_reason is not None
    # The deterministic checks themselves passed; it is the second model that held.
    v = outcome.verification
    assert v is not None
    assert v.deterministic_checks_passed is True
    assert v.second_model_agrees is False


def test_wrong_math_answer_is_refused():
    gen = ContentGenerator()
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 41.0},
    )
    outcome = gen.generate(req)
    assert outcome.served is False
    assert outcome.material is None
    assert outcome.verification.deterministic_checks_passed is False


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.99)


def test_served_only_when_gate_fully_passes():
    """Inject an agreeing second model into the spine orchestrator: now the
    deterministic-correct math item is served and carries real verified content."""
    from app.orchestrator import Orchestrator  # spine, via _spine path bootstrap

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    gen = ContentGenerator(orchestrator=orch)
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
    )
    outcome = gen.generate(req)
    assert outcome.served is True
    assert outcome.material is not None
    assert outcome.material.body.get("answer") == 42.0
    assert outcome.material.second_model_agreed is True
    assert outcome.material.confidence >= outcome.material.gate_threshold


def test_narrative_generation_refused_without_provider():
    """Explanation has no deterministic handle and no live provider => refusal,
    never a fabricated explanation."""
    gen = ContentGenerator()
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.EXPLANATION,
        payload={"prompt": "explain HCF"},
    )
    outcome = gen.generate(req)
    assert outcome.served is False
    assert outcome.material is None


def test_generate_into_repository_files_draft_only():
    from app.orchestrator import Orchestrator

    orch = Orchestrator(second_model=_AgreeingSecondModel())
    gen = ContentGenerator(orchestrator=orch)
    repo = InMemoryContentRepository()
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "10 / 2", "claimed_answer": 5.0},
        title="Division practice",
    )
    outcome, record = gen.generate_into_repository(req, repo)
    assert outcome.served is True
    assert record is not None
    # Verified body, but filed as DRAFT — never auto-published (permission ladder).
    assert record.approval_state is ApprovalState.DRAFT
    assert record.is_servable is False
    assert record.latest_version.verified_served is True


def test_withheld_generation_files_nothing():
    gen = ContentGenerator()  # abstaining second model => withheld
    repo = InMemoryContentRepository()
    req = MaterialRequest(
        topic_id="topic-1",
        kind=MaterialKind.PRACTICE_ITEM,
        payload={"expression": "6 * 7", "claimed_answer": 42.0},
    )
    outcome, record = gen.generate_into_repository(req, repo)
    assert outcome.served is False
    assert record is None
    assert repo.all() == ()
