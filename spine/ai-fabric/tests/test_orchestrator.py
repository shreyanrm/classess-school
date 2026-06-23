"""Tests for the orchestrator: generate-and-verify end to end, served vs
withheld, permission ladder, track routing. Import-safe, no network."""

from __future__ import annotations

import uuid

from app.observability import BufferingTraceSink, Tracer
from app.orchestrator import Candidate, Intent, Orchestrator, ProviderAdapter
from app.verify import ConfidenceGate


def _rid() -> str:
    return str(uuid.uuid4())


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.97)


class _GoodMathProvider:
    """Wired provider that returns a correct, verifiable math candidate."""

    def generate(self, *, capability, route, payload):
        from app.verify import MathItem
        return Candidate(
            content={"answer": 144},
            confidence=0.99,
            math_item=MathItem(expression="12 * 12", claimed_answer=144),
        )


class _WrongMathProvider:
    def generate(self, *, capability, route, payload):
        from app.verify import MathItem
        return Candidate(
            content={"answer": 140},
            confidence=0.99,
            math_item=MathItem(expression="12 * 12", claimed_answer=140),
        )


# -- served vs withheld ----------------------------------------------------

def test_served_when_deterministic_and_second_model_pass():
    orch = Orchestrator(provider=_GoodMathProvider(), second_model=_AgreeingSecondModel())
    res = orch.handle(Intent(
        request_id=_rid(), capability="content.generate-practice-item",
        purpose="practice_item_generation",
    ))
    assert res.verification is not None
    assert res.verification.served is True
    assert res.refused is False
    assert res.content == {"answer": 144}


def test_withheld_when_deterministic_fails():
    orch = Orchestrator(provider=_WrongMathProvider(), second_model=_AgreeingSecondModel())
    res = orch.handle(Intent(
        request_id=_rid(), capability="content.generate-practice-item",
        purpose="practice_item_generation",
    ))
    assert res.verification.served is False
    assert res.refused is True
    assert res.content is None
    assert "deterministic" in (res.detail or "")


def test_withheld_when_second_model_abstains_by_default():
    # No second model provided => AbstainingSecondModel => gate closed.
    orch = Orchestrator(provider=_GoodMathProvider())
    res = orch.handle(Intent(
        request_id=_rid(), capability="content.generate-practice-item",
        purpose="practice_item_generation",
    ))
    assert res.verification.served is False
    assert res.refused is True


# -- deterministic-only path (no LLM, payload carries the claim) -----------

def test_deterministic_math_provider_from_payload():
    # No wired provider; payload supplies expression + claimed_answer.
    # Second model still abstains => withheld, but deterministic checks PASS.
    orch = Orchestrator()
    res = orch.handle(Intent(
        request_id=_rid(), capability="content.generate-practice-item",
        purpose="practice_item_generation",
        payload={"expression": "7 * 6", "claimed_answer": 42},
    ))
    assert res.verification is not None
    assert res.verification.deterministic_checks_passed is True
    # Withheld only because the second model abstains (no provider).
    assert res.verification.served is False


# -- permission ladder -----------------------------------------------------

def test_consequential_capability_requires_approval():
    orch = Orchestrator(provider=_GoodMathProvider(), second_model=_AgreeingSecondModel())
    res = orch.handle(Intent(
        request_id=_rid(), capability="evaluate.response",
        purpose="response_evaluation",
        payload={"expression": "1 + 1", "claimed_answer": 2},
    ))
    assert res.requires_approval is True
    assert res.content is None
    assert res.refused is False


def test_consequential_with_approval_proceeds_to_verify():
    orch = Orchestrator(provider=_GoodMathProvider(), second_model=_AgreeingSecondModel())
    res = orch.handle(Intent(
        request_id=_rid(), capability="evaluate.response",
        purpose="response_evaluation",
        approval_token="human-approved-123",
    ))
    assert res.requires_approval is False
    assert res.verification is not None
    assert res.verification.served is True


# -- least privilege / unknown ---------------------------------------------

def test_purpose_mismatch_refused():
    orch = Orchestrator(provider=_GoodMathProvider(), second_model=_AgreeingSecondModel())
    res = orch.handle(Intent(
        request_id=_rid(), capability="content.generate-practice-item",
        purpose="wrong_purpose",
    ))
    assert res.refused is True
    assert "purpose mismatch" in (res.detail or "")


def test_unknown_capability_refused():
    orch = Orchestrator()
    res = orch.handle(Intent(request_id=_rid(), capability="nope.nope", purpose="x"))
    assert res.refused is True
    assert "unknown capability" in (res.detail or "")


# -- no provider, no deterministic handle => refusal, never fabricates -----

def test_no_provider_no_handle_refuses():
    orch = Orchestrator()  # no wired provider, payload has no math handle
    res = orch.handle(Intent(
        request_id=_rid(), capability="conversation.companion-turn",
        purpose="companion_dialogue",
    ))
    assert res.refused is True
    assert res.content is None


# -- observability ---------------------------------------------------------

def test_tracer_emits_spans_to_buffer():
    sink = BufferingTraceSink()
    orch = Orchestrator(
        provider=_GoodMathProvider(), second_model=_AgreeingSecondModel(),
        tracer=Tracer(sink=sink),
    )
    orch.handle(Intent(
        request_id=_rid(), capability="content.generate-practice-item",
        purpose="practice_item_generation",
    ))
    assert len(sink.spans) == 1
    span = sink.spans[0]
    assert span.attributes.get("router.tier") == "mid"
    assert "quality.served" in span.attributes
    assert span.latency_ms is not None


def test_tracer_noops_without_backend():
    t = Tracer(env={})
    assert t.backend_configured is False
    with t.span("x") as s:
        s.record_cost(10)
    # No backend, no raise — the span just closes.
