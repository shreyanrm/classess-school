"""Planning generators: course outline / lesson plan / session plan.

Each runs through the SAME generate-and-verify substrate as the content module —
the ai-fabric orchestrator's confidence gate (INVARIANT 7). The provider is
mocked (a structured candidate) and the second model is injected to agree, so we
exercise the FULL gate; the no-provider path is asserted to refuse, never
fabricate. Course outlines additionally pass an ontology-coverage gate.
"""

from dataclasses import dataclass

import planning  # noqa: F401 — bootstraps the spine path via the package
from planning.app.generate import (
    CAP_COURSE,
    CAP_LESSON,
    CAP_SESSION,
    PlanningContentGenerator,
)


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.99)


class _AbstainingSecondModel:
    def cross_check(self, *, task_class, content):
        return (False, 0.0)


@dataclass
class _MockProvider:
    """A provider-mock that returns a structured plan body (no symbolic oracle),
    so verification rests on the independent second-model cross-check + the gate —
    exactly the content module's narrative verification mode."""

    confidence: float = 0.99

    def generate(self, *, capability, route, payload):
        from app.orchestrator import Candidate

        body = {
            "kind": capability.name,
            "units": [{"topics": [{"title": "t", "outcomes": ["o1"]}]}],
            "objectives": ["o1"],
            "sequence": ["intro", "model", "practice"],
            "checks_for_understanding": ["exit ticket"],
            "materials": ["whiteboard"],
        }
        return Candidate(content=body, confidence=self.confidence)


def _orch(second_model, provider=None):
    from app.orchestrator import Orchestrator

    return Orchestrator(second_model=second_model, provider=provider or _MockProvider())


def _resolver(known):
    return lambda ref: ref.outcome_id in set(known)


# --------------------------------------------------------------------------- #
# COURSE OUTLINE — generate + verify against ontology coverage + the gate
# --------------------------------------------------------------------------- #

def test_course_outline_served_when_coverage_and_gate_pass():
    g = PlanningContentGenerator(
        orchestrator=_orch(_AgreeingSecondModel()),
        resolve_outcome=_resolver({"o1", "o2"}),
    )
    out = g.generate_course_outline("subject-1", {"grade": 9}, ["o1", "o2"])
    assert out.served is True
    assert out.capability == CAP_COURSE
    assert out.confidence is not None and out.confidence >= out.gate_threshold
    assert out.unresolved_outcomes == ()
    assert out.body is not None


def test_course_outline_withheld_on_ontology_coverage_failure():
    """An outline naming an outcome that does NOT resolve in the ontology is
    withheld BEFORE generation — never served against a phantom outcome."""
    g = PlanningContentGenerator(
        orchestrator=_orch(_AgreeingSecondModel()),
        resolve_outcome=_resolver({"o1"}),
    )
    out = g.generate_course_outline("subject-1", {"grade": 9}, ["o1", "o9"])
    assert out.served is False
    assert out.unresolved_outcomes == ("o9",)
    assert "o9" in (out.review_reason or "")


def test_course_outline_withheld_by_confidence_gate():
    """Coverage passes but the second model abstains => the confidence gate
    withholds. Proves the gate is honoured, not bypassed."""
    g = PlanningContentGenerator(
        orchestrator=_orch(_AbstainingSecondModel()),
        resolve_outcome=_resolver({"o1"}),
    )
    out = g.generate_course_outline("subject-1", {"grade": 9}, ["o1"])
    assert out.served is False
    assert out.unresolved_outcomes == ()  # coverage was fine; the GATE held


# --------------------------------------------------------------------------- #
# LESSON PLAN — adaptive, engagement/model-aware, prepared (not published)
# --------------------------------------------------------------------------- #

def test_lesson_plan_served_through_gate_as_prepared_draft():
    g = PlanningContentGenerator(orchestrator=_orch(_AgreeingSecondModel()))
    out = g.generate_lesson_plan(
        "topic-1", {"instructional_model": "5E", "engagement": "high"}
    )
    assert out.served is True
    assert out.capability == CAP_LESSON
    assert out.requires_approval is False  # PREPARE rung — prepared, not published
    assert out.body is not None


def test_lesson_plan_withheld_when_gate_does_not_pass():
    g = PlanningContentGenerator(orchestrator=_orch(_AbstainingSecondModel()))
    out = g.generate_lesson_plan("topic-1", {"instructional_model": "5E"})
    assert out.served is False
    assert out.body is None
    assert out.review_reason is not None


def test_lesson_plan_refuses_without_provider_never_fabricates():
    """No provider and no live key => a clean refusal that names the env var,
    never a fabricated plan."""
    g = PlanningContentGenerator(resolve_outcome=_resolver({"o1"}))  # default orchestrator
    out = g.generate_lesson_plan("topic-1", {"prompt": "plan a lesson"})
    assert out.served is False
    assert out.body is None


# --------------------------------------------------------------------------- #
# SESSION / PERIOD PLAN — derived from a lesson plan + a timetable slot
# --------------------------------------------------------------------------- #

def test_session_plan_served_through_gate():
    g = PlanningContentGenerator(orchestrator=_orch(_AgreeingSecondModel()))
    lesson = g.generate_lesson_plan("topic-1", {"instructional_model": "5E"})
    assert lesson.served is True
    out = g.generate_session_plan(lesson.body, {"period": 3, "minutes": 40})
    assert out.served is True
    assert out.capability == CAP_SESSION
    assert out.requires_approval is False
    assert out.body is not None


def test_session_plan_withheld_by_gate():
    g = PlanningContentGenerator(orchestrator=_orch(_AbstainingSecondModel()))
    out = g.generate_session_plan({"objectives": ["o1"]}, {"period": 1, "minutes": 40})
    assert out.served is False
    assert out.body is None
