"""Generate supporting material against the ontology, VERIFIED before use (B3).

INVARIANT 7 — nothing generated is served unverified. This module is a thin
content-shaped wrapper over the ai-fabric orchestrator's generate-and-verify
substrate (``spine/ai-fabric``). It never re-implements the confidence gate; it
delegates to it and honours its verdict:

  - the orchestrator routes on the owning track, runs deterministic checks
    FIRST (symbolic/numeric for math/physics), then a second-model cross-check,
    then the confidence gate;
  - only content whose ``verification.served`` is True is returned as generated
    material. A withheld result is returned as a refusal carrying the review
    reason — it is routed to the human verification surface, never served.

With no live LLM key the orchestrator returns a clearly-marked refusal for
narrative material (it does not fabricate), while math/physics items with a
checkable expression + claimed answer still pass through the REAL deterministic
arithmetic verifier in the spine. So the deterministic path produces genuinely
verified content offline, and everything else degrades to a refusal that names
the env var to set — never an invented answer.

The provider key the live path will read is owned by the ai-fabric router and
named there (``clss.aifabric.dev.track1_provider_key``); this module names no
key of its own and holds no credentials (INVARIANT 8 — agents hold no creds).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from . import _spine
from .hyperlocalize import (
    Hyperlocalizer,
    LocaleContext,
    LocalizationProvider,
)
from .repository import (
    ApprovalState,
    ContentKind,
    ContentRecord,
    InMemoryContentRepository,
    LicenceMetadata,
)


# ---------------------------------------------------------------------------
# Material shapes
# ---------------------------------------------------------------------------

class MaterialKind(str, Enum):
    """The kinds of supporting material this module can request generation of."""

    EXPLANATION = "explanation"
    WORKED_EXAMPLE = "worked_example"
    PRACTICE_ITEM = "practice_item"
    # An interactive teaching visual (a plotted curve y = f(x), JSXGraph/Mafs-
    # shaped). Verified deterministically: the curve is re-evaluated at its
    # sample points before it is served (INVARIANT 7).
    LESSON_VISUAL = "lesson_visual"


# Map a material kind to the ai-fabric capability that produces it. Only the
# practice-item capability exists in the default spine registry today; the
# others name the capability they will bind to. Unknown -> refusal, never
# fabricated routing.
_KIND_TO_CAPABILITY: dict[MaterialKind, str] = {
    MaterialKind.PRACTICE_ITEM: "content.generate-practice-item",
    MaterialKind.WORKED_EXAMPLE: "content.generate-practice-item",
    MaterialKind.EXPLANATION: "explain.step",
    MaterialKind.LESSON_VISUAL: "content.generate-lesson-visual",
}

# The purpose code each capability runs under (must match the registry's
# least-privilege purpose, or the orchestrator refuses on a purpose mismatch).
_CAPABILITY_PURPOSE: dict[str, str] = {
    "content.generate-practice-item": "practice_item_generation",
    "explain.step": "step_explanation",
    "content.generate-lesson-visual": "lesson_visual_generation",
}


@dataclass(frozen=True)
class MaterialRequest:
    """A request to generate supporting material for an ontology topic.

    ``payload`` is handed to the orchestrator. For a math/physics item, include
    ``expression`` and ``claimed_answer`` (and optional bounds/units) so the
    DETERMINISTIC verifier can produce real, verified content with no LLM. Other
    payload shapes are routed to the live provider when one is configured, and
    otherwise refused (never fabricated).
    """

    topic_id: str
    kind: MaterialKind
    payload: dict[str, object] = field(default_factory=dict)
    difficulty: float | None = None
    latency_sensitive: bool | None = None
    title: str | None = None
    outcome_ids: tuple[str, ...] = ()
    # Hyperlocalization (optional). When ``locale`` is set, the VERIFIED body is
    # run through the hyperlocalization generate-and-verify path before it is
    # returned. ``subject_terms`` are the terms that must survive verbatim
    # (photosynthesis stays photosynthesis). Board is a FIELD on ``locale``.
    locale: LocaleContext | None = None
    subject_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedMaterial:
    """A piece of generated material that PASSED the confidence gate."""

    topic_id: str
    kind: MaterialKind
    body: dict[str, object]
    confidence: float
    gate_threshold: float
    deterministic_summary: str
    second_model_agreed: bool
    request_id: str
    tier: str | None
    track: int | None
    # Hyperlocalization status of ``body``. ``localized`` is True when a verified
    # localised variant was served; ``not_yet_localised`` True when the base
    # (verified) body is served because no provider was wired or the variant was
    # withheld. Both bodies are always verified — never a fabricated translation.
    localized: bool = False
    not_yet_localised: bool = False
    locale: LocaleContext | None = None


@dataclass(frozen=True)
class GenerationOutcome:
    """The outcome of a generation attempt.

    Exactly one of ``material`` / refusal is meaningful:
      - ``served`` True  => ``material`` is set, gate passed, safe to use.
      - ``served`` False => ``material`` is None and ``review_reason`` explains
        why the gate withheld it; route to the human verification surface.
    """

    served: bool
    request_id: str
    material: GeneratedMaterial | None
    provider_available: bool
    requires_approval: bool
    review_reason: str | None
    # The full spine verification block, when one was produced (None on a hard
    # refusal such as an unknown capability or unavailable provider).
    verification: object | None = None


def _new_request_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------

class ContentGenerator:
    """Generates supporting material via ai-fabric; serves only verified output.

    Holds NO provider and NO credentials by default — it constructs a spine
    ``Orchestrator`` (which, with no live key, refuses narrative generation and
    runs the deterministic verifier for math/physics). A live provider adapter
    can be injected later; it is wired into the spine orchestrator, never here.
    """

    def __init__(
        self,
        orchestrator: object | None = None,
        localization_provider: LocalizationProvider | None = None,
        localization_second_model: object | None = None,
    ) -> None:
        self._spine_available = _spine.SPINE_AVAILABLE
        if orchestrator is not None:
            self._orchestrator = orchestrator
        elif self._spine_available:
            # Default spine orchestrator: no provider => deterministic-only.
            self._orchestrator = _spine.Orchestrator()  # type: ignore[operator]
        else:  # pragma: no cover - only when the spine is genuinely absent
            self._orchestrator = None
        # The hyperlocalizer runs AFTER the content gate, on already-verified
        # bodies. When no provider is injected, attempt to AUTO-WIRE the REAL
        # Gemini-backed provider from the environment (key read by NAME). With no
        # key it returns None, so the hyperlocalizer degrades to its existing
        # deterministic/template path — base content served not-yet-localised,
        # never a fabricated localised variant.
        if localization_provider is None:
            from .gemini_localization import make_localization_provider

            localization_provider = make_localization_provider()
        self._hyperlocalizer = Hyperlocalizer(
            provider=localization_provider,
            second_model=localization_second_model,
        )

    @property
    def available(self) -> bool:
        """True when the ai-fabric substrate is importable and wired."""
        return self._orchestrator is not None

    def generate(self, request: MaterialRequest) -> GenerationOutcome:
        """Run generate-and-verify for one material request.

        Returns a served material only when the spine's confidence gate passes.
        """
        request_id = _new_request_id()

        if not self.available:  # pragma: no cover - spine missing
            return GenerationOutcome(
                served=False, request_id=request_id, material=None,
                provider_available=False, requires_approval=False,
                review_reason=(
                    "ai-fabric substrate unavailable; cannot verify, so nothing is served. "
                    "This is a graceful refusal, not a fabricated answer."
                ),
            )

        capability = _KIND_TO_CAPABILITY.get(request.kind)
        if capability is None:
            return GenerationOutcome(
                served=False, request_id=request_id, material=None,
                provider_available=False, requires_approval=False,
                review_reason=f"no capability bound for material kind '{request.kind.value}'.",
            )
        purpose = _CAPABILITY_PURPOSE[capability]

        intent = _spine.Intent(  # type: ignore[operator]
            request_id=request_id,
            capability=capability,
            purpose=purpose,
            payload=dict(request.payload),
            difficulty=request.difficulty,
            latency_sensitive=request.latency_sensitive,
        )
        result = self._orchestrator.handle(intent)  # type: ignore[union-attr]

        verification = getattr(result, "verification", None)
        served = bool(getattr(result, "content", None) is not None and verification is not None
                      and getattr(verification, "served", False))

        if not served:
            return GenerationOutcome(
                served=False, request_id=request_id, material=None,
                provider_available=bool(getattr(result, "provider_available", False)),
                requires_approval=bool(getattr(result, "requires_approval", False)),
                review_reason=getattr(result, "detail", None)
                or getattr(verification, "review_reason", None)
                or "withheld by the confidence gate.",
                verification=verification,
            )

        det_checks = getattr(verification, "deterministic_checks", []) or []
        det_summary = "; ".join(
            f"{c.name}={'pass' if c.passed else 'fail'}" for c in det_checks
        ) or "no deterministic checks"

        verified_body = (
            dict(result.content) if isinstance(result.content, dict)
            else {"value": result.content}
        )

        # HYPERLOCALIZATION (optional): when a locale is requested, run the
        # VERIFIED body through the hyperlocalization generate-and-verify path.
        # Only a verified localised variant is served; otherwise the base
        # verified body is served, marked not-yet-localised (graceful degrade).
        served_body = verified_body
        localized = False
        not_yet_localised = False
        if request.locale is not None:
            hl = self._hyperlocalizer.hyperlocalize(
                body=verified_body,
                locale=request.locale,
                subject_terms=request.subject_terms,
            )
            served_body = hl.body
            localized = hl.localized
            not_yet_localised = hl.not_yet_localised

        material = GeneratedMaterial(
            topic_id=request.topic_id,
            kind=request.kind,
            body=served_body,
            confidence=float(getattr(verification, "confidence", 0.0)),
            gate_threshold=float(getattr(verification, "gate_threshold", 0.0)),
            deterministic_summary=det_summary,
            second_model_agreed=bool(getattr(verification, "second_model_agrees", False)),
            request_id=request_id,
            tier=getattr(result, "tier", None),
            track=getattr(result, "track", None),
            localized=localized,
            not_yet_localised=not_yet_localised,
            locale=request.locale,
        )
        return GenerationOutcome(
            served=True, request_id=request_id, material=material,
            provider_available=bool(getattr(result, "provider_available", False)),
            requires_approval=False, review_reason=None, verification=verification,
        )

    # -- repository integration -------------------------------------------

    def generate_into_repository(
        self,
        request: MaterialRequest,
        repository: InMemoryContentRepository,
    ) -> tuple[GenerationOutcome, ContentRecord | None]:
        """Generate and, on success, file a DRAFT content record.

        The record is created as a DRAFT carrying the verified body. It is NOT
        auto-approved or made live: publishing to learners is an explicit human
        act through the verification surface (INVARIANT 8 — the permission
        ladder; agents prepare, humans approve). A withheld generation files
        nothing and returns no record.
        """
        outcome = self.generate(request)
        if not outcome.served or outcome.material is None:
            return outcome, None

        kind_map = {
            MaterialKind.EXPLANATION: ContentKind.EXPLANATION,
            MaterialKind.WORKED_EXAMPLE: ContentKind.WORKED_EXAMPLE,
            MaterialKind.PRACTICE_ITEM: ContentKind.PRACTICE_ITEM,
            MaterialKind.LESSON_VISUAL: ContentKind.DIAGRAM,
        }
        record = repository.create(
            topic_id=request.topic_id,
            kind=kind_map[request.kind],
            title=request.title or f"{request.kind.value} for topic {request.topic_id}",
            body=outcome.material.body,
            licence=LicenceMetadata.for_generated(),
            author="system:generate",
            verified_served=True,  # this body passed the gate
            verification_summary=outcome.material.deterministic_summary,
            source_request_id=outcome.request_id,
            outcome_ids=request.outcome_ids,
        )
        # Created as DRAFT; a human moves it through IN_REVIEW -> APPROVED.
        assert record.approval_state is ApprovalState.DRAFT
        return outcome, record
