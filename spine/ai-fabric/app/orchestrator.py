"""The Vidya orchestrator entrypoint (A4) — thin.

Routes an INTENT to a capability, runs GENERATE-AND-VERIFY, and returns a
structured result carrying the verification block.

Permission-ladder aware (INVARIANT 8): a CONSEQUENTIAL capability (one that
sends / submits / publishes / deletes / charges / GRADES) returns a
``requires_approval`` result rather than executing. Approval is an explicit
human act represented by an ``approval_token``; the orchestrator never holds
credentials and never self-approves.

Generation flow:
  1. resolve the capability from the registry (least-privilege),
  2. permission-ladder check — consequential => requires_approval,
  3. route to a tier on the OWNING track (INVARIANT 11),
  4. if the provider is unavailable => a well-formed REFUSAL (never fabricates),
  5. obtain candidate content from the provider adapter (or the deterministic
     stand-in for math/physics with a known solution),
  6. run deterministic checks, then the second-model cross-check,
  7. apply the CONFIDENCE GATE — served only if it passes,
  8. return a structured GenerateResult with the verification block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .cache import VerifiedResponseCache
from .capability_registry import Capability, CapabilityRegistry, default_registry
from .observability import Tracer
from .retrieval import NullRetriever, RetrievedContext, Retriever
from .router import (
    ModelRouter,
    RouteResolution,
    RouterSelectionInput,
    Track1Config,
    Track2Config,
)
from .second_model import make_second_model
from .verify import (
    ConfidenceGate,
    DeterministicCheck,
    GenerateVerification,
    LessonVisualItem,
    MathItem,
    SecondModelChecker,
    deterministic_checks_for_math,
    deterministic_checks_for_visual,
)


# ---------------------------------------------------------------------------
# Intent / result shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    """An intent handed to the orchestrator."""

    request_id: str
    capability: str
    purpose: str
    payload: dict[str, object] = field(default_factory=dict)
    # An explicit human-approval token for consequential capabilities.
    approval_token: str | None = None
    # Routing signals (complexity + latency + cost + context).
    difficulty: float | None = None
    latency_sensitive: bool | None = None
    cost_sensitive: bool | None = None
    context_tokens: int | None = None
    # An optional retrieval query; when set, the retriever grounds generation.
    retrieval_query: str | None = None


@dataclass(frozen=True)
class GenerateResult:
    """The orchestrator's structured result. Mirrors the contract shape."""

    request_id: str
    capability: str
    content: object | None
    verification: GenerateVerification | None
    refused: bool
    provider_available: bool
    requires_approval: bool = False
    detail: str | None = None
    tier: str | None = None
    track: int | None = None
    # True when the verified artifact was served straight from the response cache.
    cache_hit: bool = False
    # How many grounding snippets the retrieval hook supplied (0 when ungrounded).
    retrieved: int = 0


# ---------------------------------------------------------------------------
# Provider adapter interface
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    """A candidate generation plus any deterministic-checkable claims."""

    content: object
    confidence: float
    # For math/physics items: the deterministic ground-truth handle.
    math_item: MathItem | None = None
    # For a lesson visual (plotted curve): the deterministic ground-truth handle.
    visual_item: LessonVisualItem | None = None
    # Token usage if the provider reports it (None when unavailable). Recorded on
    # the trace span; never required for the deterministic paths.
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ProviderAdapter(Protocol):
    """Produces a candidate for a routed capability. With no live key the router
    short-circuits before this is ever called, so adapters never see credentials
    they do not have."""

    def generate(self, *, capability: Capability, route: RouteResolution, payload: dict) -> Candidate:
        ...


@dataclass
class DeterministicMathProvider:
    """A no-LLM provider for math/physics intents whose payload carries an
    expression + claimed answer. Lets the deterministic path produce real,
    verifiable content with no external provider — used for tests and as the
    safe local fallback."""

    confidence: float = 0.99

    def generate(self, *, capability: Capability, route: RouteResolution, payload: dict) -> Candidate:
        expression = str(payload["expression"])
        claimed = float(payload["claimed_answer"])
        item = MathItem(
            expression=expression,
            claimed_answer=claimed,
            answer_lower=payload.get("answer_lower"),
            answer_upper=payload.get("answer_upper"),
            claimed_unit=payload.get("claimed_unit"),
            expected_unit=payload.get("expected_unit"),
        )
        return Candidate(
            content={"expression": expression, "answer": claimed, "unit": payload.get("claimed_unit")},
            confidence=self.confidence,
            math_item=item,
        )


@dataclass
class DeterministicVisualProvider:
    """A no-LLM provider for a LESSON VISUAL (a plotted curve y = f(x)) whose
    payload carries an ``expression`` + plotted ``samples``. Lets the
    deterministic plotted-point path produce a real, verifiable teaching visual
    with no external provider — the visual analogue of the math stand-in."""

    confidence: float = 0.99

    def generate(self, *, capability: Capability, route: RouteResolution, payload: dict) -> Candidate:
        expression = str(payload["expression"])
        var = str(payload.get("var", "x"))
        samples = tuple(
            (float(x), float(y)) for x, y in payload["samples"]
        )
        item = LessonVisualItem(
            expression=expression,
            samples=samples,
            var=var,
            x_min=payload.get("x_min"),
            x_max=payload.get("x_max"),
            y_min=payload.get("y_min"),
            y_max=payload.get("y_max"),
        )
        return Candidate(
            content={
                "kind": "lesson_visual",
                "plot": {"expression": expression, "var": var},
                "points": [{"x": x, "y": y} for x, y in samples],
            },
            confidence=self.confidence,
            visual_item=item,
        )


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Thin Vidya orchestrator entrypoint."""

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        router: ModelRouter | None = None,
        gate: ConfidenceGate | None = None,
        second_model: SecondModelChecker | None = None,
        provider: ProviderAdapter | None = None,
        tracer: Tracer | None = None,
        cache: VerifiedResponseCache | None = None,
        retriever: Retriever | None = None,
    ) -> None:
        self.registry = registry if registry is not None else default_registry()
        self.router = router if router is not None else ModelRouter()
        self.gate = gate if gate is not None else ConfidenceGate()
        # The response cache holds ONLY verified artifacts (INVARIANT 7); a hit
        # returns a gate-cleared artifact without re-running generation/verify.
        self.cache = cache if cache is not None else VerifiedResponseCache()
        # The retrieval hook grounds generation; defaults to no grounding.
        self.retriever = retriever if retriever is not None else NullRetriever()
        # The factory wires the LIVE second-model cross-check when the
        # cross-check provider key is present (by NAME) and a seam is available;
        # otherwise it returns the abstaining model so the gate stays closed and
        # no unverified content is served (INVARIANT 7).
        self.second_model = second_model if second_model is not None else make_second_model()
        self.provider = provider  # None => deterministic-only / unavailable
        self.tracer = tracer if tracer is not None else Tracer()

    def handle(self, intent: Intent) -> GenerateResult:
        cap = self.registry.get(intent.capability)
        if cap is None:
            return GenerateResult(
                request_id=intent.request_id, capability=intent.capability,
                content=None, verification=None, refused=True,
                provider_available=False,
                detail=f"unknown capability: {intent.capability!r}",
            )

        # Least-privilege: the declared purpose must match the intent purpose.
        if cap.least_privilege.purpose != intent.purpose:
            return GenerateResult(
                request_id=intent.request_id, capability=cap.name,
                content=None, verification=None, refused=True,
                provider_available=False,
                detail=(
                    f"purpose mismatch: capability runs under "
                    f"'{cap.least_privilege.purpose}', intent declared '{intent.purpose}'."
                ),
            )

        with self.tracer.span("orchestrator.handle", capability=cap.name, track=cap.track) as span:
            # PERMISSION LADDER: consequential => require explicit approval.
            if cap.is_consequential and not intent.approval_token:
                span.set("permission.requires_approval", True)
                return GenerateResult(
                    request_id=intent.request_id, capability=cap.name,
                    content=None, verification=None, refused=False,
                    provider_available=False, requires_approval=True,
                    track=cap.track,
                    detail=(
                        f"'{cap.name}' is consequential ({cap.consequence.value}); "
                        "explicit human approval (approval_token) is required before execution."
                    ),
                )

            # ROUTE on the OWNING track (INVARIANT 11 — never crosses).
            # The router weighs complexity + latency + cost + context.
            route = self.router.resolve(RouterSelectionInput(
                task_class=cap.task_class,
                requires_verification=cap.requires_verification,
                difficulty=intent.difficulty,
                latency_sensitive=intent.latency_sensitive,
                cost_sensitive=intent.cost_sensitive,
                context_tokens=intent.context_tokens,
                track=cap.track,
            ))
            span.set("router.tier", route.selection.tier.value)
            span.set("router.track", route.selection.track)
            if route.model is not None:
                span.record_model(route.model.model_label)

            # Resolve the provider: explicit adapter, else deterministic math
            # stand-in when the payload supports it.
            provider = self._provider_for(intent)

            if not route.available and provider is None:
                # No live provider AND no deterministic stand-in => refusal.
                return GenerateResult(
                    request_id=intent.request_id, capability=cap.name,
                    content=None, verification=None, refused=True,
                    provider_available=False, track=cap.track,
                    tier=route.selection.tier.value,
                    detail=route.unavailable_reason
                    or f"no provider available; set env var for '{route.provider_key_env}'.",
                )

            if provider is None:
                return GenerateResult(
                    request_id=intent.request_id, capability=cap.name,
                    content=None, verification=None, refused=True,
                    provider_available=route.available, track=cap.track,
                    tier=route.selection.tier.value,
                    detail="no provider adapter wired for this capability.",
                )

            # RETRIEVAL hook: ground the request before generation. The snippets
            # are passed to the provider via the payload (a real adapter folds
            # them into its prompt); the count is recorded on the span.
            contexts = self._retrieve(intent, cap.task_class)
            span.set("retrieval.count", len(contexts))
            payload = dict(intent.payload)
            if contexts:
                payload["_retrieved_context"] = [c.text for c in contexts]

            candidate = provider.generate(capability=cap, route=route, payload=payload)
            # Tokens are recorded only when the provider reported them.
            if candidate.prompt_tokens is not None or candidate.completion_tokens is not None:
                span.record_tokens(
                    prompt=candidate.prompt_tokens,
                    completion=candidate.completion_tokens,
                )

            tier = route.selection.tier.value

            # RESPONSE CACHE: keyed by the VERIFIED-CONTENT hash. A hit returns a
            # gate-cleared artifact without re-running the second model — only
            # verified content ever entered the cache (INVARIANT 7).
            cached = self.cache.get(
                capability=cap.name, task_class=cap.task_class, tier=tier,
                payload=intent.payload, content=candidate.content,
            )
            if cached is not None:
                span.record_cache_hit(True)
                span.record_quality(served=True, confidence=cached.confidence)
                verification = GenerateVerification(
                    deterministic_checks=[],
                    deterministic_checks_passed=True,
                    second_model_agrees=True,
                    confidence=cached.confidence,
                    gate_threshold=self.gate.threshold,
                    served=True,
                    review_reason=None,
                )
                return GenerateResult(
                    request_id=intent.request_id, capability=cap.name,
                    content=cached.content, verification=verification,
                    refused=False, provider_available=True,
                    track=cap.track, tier=tier, cache_hit=True,
                    retrieved=len(contexts),
                )
            span.record_cache_hit(False)

            # GENERATE-AND-VERIFY: deterministic checks FIRST.
            det_checks = self._deterministic_checks(candidate)
            agrees, sm_conf = self.second_model.cross_check(
                task_class=cap.task_class, content=candidate.content
            )
            # Aggregate confidence: combine generator confidence with the
            # second-model signal (min — the gate is conservative). When the
            # second model abstains (does not agree), its zero confidence pulls
            # the aggregate down and the gate closes on confidence too.
            confidence = min(candidate.confidence, sm_conf)

            verification = self.gate.evaluate(det_checks, agrees, confidence)
            span.record_quality(served=verification.served, confidence=confidence)

            content = candidate.content if verification.served else None
            # Only a VERIFIED artifact is cached (INVARIANT 7).
            if verification.served:
                self.cache.put(
                    capability=cap.name, task_class=cap.task_class, tier=tier,
                    payload=intent.payload, content=candidate.content,
                    confidence=confidence,
                )
            return GenerateResult(
                request_id=intent.request_id, capability=cap.name,
                content=content, verification=verification,
                refused=not verification.served,
                provider_available=True,
                track=cap.track, tier=tier, cache_hit=False,
                retrieved=len(contexts),
                detail=None if verification.served else verification.review_reason,
            )

    # -- helpers -----------------------------------------------------------

    def _retrieve(self, intent: Intent, task_class: str) -> list[RetrievedContext]:
        """Run the retrieval hook for the intent's query, if any. Never raises
        into the pipeline — a retrieval error degrades to ungrounded generation."""
        if not intent.retrieval_query:
            return []
        try:
            return self.retriever.retrieve(query=intent.retrieval_query, task_class=task_class)
        except Exception:
            return []

    def _provider_for(self, intent: Intent) -> ProviderAdapter | None:
        if self.provider is not None:
            return self.provider
        # Deterministic math stand-in: available without any LLM when the
        # payload carries an expression + claimed answer.
        if "expression" in intent.payload and "claimed_answer" in intent.payload:
            return DeterministicMathProvider()
        # Deterministic lesson-visual stand-in: a plotted curve y = f(x) with the
        # sample points the generator claims lie on it — verified by recompute.
        if "expression" in intent.payload and "samples" in intent.payload:
            return DeterministicVisualProvider()
        return None

    @staticmethod
    def _deterministic_checks(candidate: Candidate) -> list[DeterministicCheck]:
        if candidate.math_item is not None:
            return deterministic_checks_for_math(candidate.math_item)
        if candidate.visual_item is not None:
            return deterministic_checks_for_visual(candidate.visual_item)
        # No deterministic handle => a single failing check, so the gate stays
        # closed unless a checkable claim was provided (fail closed).
        return [DeterministicCheck(
            "deterministic-checkable", False,
            "no deterministic handle on this content; cannot verify symbolically/numerically.",
        )]
