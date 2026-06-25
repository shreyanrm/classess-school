"""LLM-generated planning artifacts, VERIFIED before use (d6 + INVARIANT 7).

Three generators, each through the SAME generate-and-verify path the content
module uses — delegate to the ai-fabric orchestrator's confidence gate; never
re-implement it:

  1. COURSE OUTLINE — units -> topics -> outcomes, generated then VERIFIED
     against the ontology: every outcome the outline claims must RESOLVE in the
     ontology snapshot (a deterministic coverage oracle). An outline that names
     an unresolved outcome is withheld, never served.
  2. LESSON PLAN — an adaptive lesson plan for a topic (objectives, sequence,
     checks-for-understanding, materials), engagement/instructional-model aware.
     Prepared as a DRAFT, approval-routed — never auto-published.
  3. SESSION (PERIOD) PLAN — a single-period plan derived from a lesson plan +
     a timetable slot. Prepared as a DRAFT, approval-routed.

The narrative bodies (lesson/session plans) have no symbolic oracle, so — like
the content module's explanation path — verification rests on the INDEPENDENT
second-model cross-check + the confidence gate inside the orchestrator. With no
provider the orchestrator refuses (never fabricates a plan). The course outline
additionally carries the ontology-coverage check as a planning-side gate.

This module holds NO credentials (INVARIANT 8); it constructs a spine
``Orchestrator`` (no provider => refuses narrative, the provider/key is owned by
the ai-fabric router). Plans are PREPARED, not published (the permission ladder).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from . import _spine
from .plans import OutcomeRef, Plan, PlanGenerator, PlanItem, PlanScope


# Each planning capability + the least-privilege purpose it runs under (must
# match the registry, or the orchestrator refuses on a purpose mismatch).
CAP_COURSE = "planning.generate-course-outline"
CAP_LESSON = "planning.generate-lesson-plan"
CAP_SESSION = "planning.generate-session-plan"

_CAPABILITY_PURPOSE: dict[str, str] = {
    CAP_COURSE: "course_outline_generation",
    CAP_LESSON: "lesson_plan_generation",
    CAP_SESSION: "session_plan_generation",
}


# ---------------------------------------------------------------------------
# Outcome shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanningOutcome:
    """The outcome of a planning-generation attempt.

    ``served`` True => ``body`` carries the verified plan and is safe to PREPARE
    as a draft (never auto-published). ``served`` False => ``body`` is None and
    ``review_reason`` explains the withholding (route to human review)."""

    served: bool
    request_id: str
    capability: str
    body: dict[str, object] | None
    confidence: float | None
    gate_threshold: float | None
    provider_available: bool
    requires_approval: bool
    review_reason: str | None
    verification: object | None = None
    # Course-outline only: outcomes the outline named that did NOT resolve in the
    # ontology. Non-empty => the coverage oracle failed and nothing is served.
    unresolved_outcomes: tuple[str, ...] = ()


def _new_request_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------

class PlanningContentGenerator:
    """Generates planning artifacts via ai-fabric; serves only verified output.

    Holds NO provider/credentials by default. ``resolve_outcome`` is the injected
    ontology predicate (does this opaque outcome id resolve?) used for the course
    outline's coverage verification — the same resolver shape ``PlanGenerator``
    already accepts. With no resolver, coverage cannot be asserted, so a course
    outline is withheld (evidence over assertion).
    """

    def __init__(
        self,
        orchestrator: object | None = None,
        resolve_outcome: Optional[Callable[[OutcomeRef], bool]] = None,
    ) -> None:
        self._spine_available = _spine.SPINE_AVAILABLE
        if orchestrator is not None:
            self._orchestrator = orchestrator
        elif self._spine_available:
            self._orchestrator = _spine.Orchestrator()  # type: ignore[operator]
        else:  # pragma: no cover - only when the spine is genuinely absent
            self._orchestrator = None
        self._resolve = resolve_outcome

    @property
    def available(self) -> bool:
        return self._orchestrator is not None

    # -- shared generate-and-verify -----------------------------------------

    def _run(
        self, capability: str, payload: dict[str, object],
        *, difficulty: float | None = None, approval_token: str | None = None,
    ) -> tuple[PlanningOutcome, object | None]:
        """Route one intent through the orchestrator's confidence gate.

        Returns ``(outcome, verification)``. The orchestrator runs deterministic
        checks where an oracle exists, the independent second-model cross-check,
        then the confidence gate — nothing unverified is served (INVARIANT 7).
        """
        request_id = _new_request_id()
        if not self.available:  # pragma: no cover - spine missing
            return PlanningOutcome(
                served=False, request_id=request_id, capability=capability,
                body=None, confidence=None, gate_threshold=None,
                provider_available=False, requires_approval=False,
                review_reason=(
                    "ai-fabric substrate unavailable; cannot verify, so nothing "
                    "is served. A graceful refusal, not a fabricated plan."
                ),
            ), None

        intent = _spine.Intent(  # type: ignore[operator]
            request_id=request_id,
            capability=capability,
            purpose=_CAPABILITY_PURPOSE[capability],
            payload=dict(payload),
            difficulty=difficulty,
            approval_token=approval_token,
        )
        result = self._orchestrator.handle(intent)  # type: ignore[union-attr]
        verification = getattr(result, "verification", None)
        served = bool(
            getattr(result, "content", None) is not None
            and verification is not None
            and getattr(verification, "served", False)
        )
        if not served:
            return PlanningOutcome(
                served=False, request_id=request_id, capability=capability,
                body=None, confidence=None, gate_threshold=None,
                provider_available=bool(getattr(result, "provider_available", False)),
                requires_approval=bool(getattr(result, "requires_approval", False)),
                review_reason=getattr(result, "detail", None)
                or getattr(verification, "review_reason", None)
                or "withheld by the confidence gate.",
                verification=verification,
            ), verification

        body = (
            dict(result.content) if isinstance(result.content, dict)
            else {"value": result.content}
        )
        return PlanningOutcome(
            served=True, request_id=request_id, capability=capability,
            body=body,
            confidence=float(getattr(verification, "confidence", 0.0)),
            gate_threshold=float(getattr(verification, "gate_threshold", 0.0)),
            provider_available=bool(getattr(result, "provider_available", False)),
            requires_approval=False, review_reason=None, verification=verification,
        ), verification

    # -- course outline -----------------------------------------------------

    def generate_course_outline(
        self,
        subject_uuid: str,
        outline_payload: dict[str, object],
        claimed_outcome_ids: Sequence[str],
        *,
        difficulty: float | None = None,
    ) -> PlanningOutcome:
        """Generate + verify a course outline (units -> topics -> outcomes).

        Two gates, both must pass (INVARIANT 7):
          1. ONTOLOGY COVERAGE (planning-side, deterministic): every outcome the
             outline claims must resolve via ``resolve_outcome``. Any unresolved
             id withholds the outline — never served against a phantom outcome.
          2. The orchestrator's confidence gate (independent second-model
             cross-check + confidence threshold) on the generated body.
        """
        # Gate 1: ontology coverage. Assert BEFORE serving — evidence over
        # assertion. No resolver => cannot assert coverage => withhold.
        unresolved: list[str] = []
        if self._resolve is None:
            return PlanningOutcome(
                served=False, request_id=_new_request_id(), capability=CAP_COURSE,
                body=None, confidence=None, gate_threshold=None,
                provider_available=False, requires_approval=False,
                review_reason=(
                    "no ontology resolver configured; course coverage cannot be "
                    "verified, so the outline is withheld."
                ),
            )
        for oid in claimed_outcome_ids:
            if not self._resolve(OutcomeRef(outcome_id=str(oid))):
                unresolved.append(str(oid))
        if unresolved:
            return PlanningOutcome(
                served=False, request_id=_new_request_id(), capability=CAP_COURSE,
                body=None, confidence=None, gate_threshold=None,
                provider_available=False, requires_approval=False,
                review_reason=(
                    "course outline names outcomes that do not resolve in the "
                    f"ontology: {', '.join(unresolved)}"
                ),
                unresolved_outcomes=tuple(unresolved),
            )

        # Gate 2: the orchestrator's confidence gate.
        payload = dict(outline_payload)
        payload.setdefault("subject_uuid", subject_uuid)
        payload.setdefault("claimed_outcome_ids", list(claimed_outcome_ids))
        outcome, _ = self._run(CAP_COURSE, payload, difficulty=difficulty)
        # Carry the coverage result onto the served outcome too (all resolved).
        if outcome.served:
            return PlanningOutcome(
                served=True, request_id=outcome.request_id, capability=CAP_COURSE,
                body=outcome.body, confidence=outcome.confidence,
                gate_threshold=outcome.gate_threshold,
                provider_available=outcome.provider_available,
                requires_approval=False, review_reason=None,
                verification=outcome.verification, unresolved_outcomes=(),
            )
        return outcome

    def outline_to_plan(
        self, outline_body: dict[str, object], plan_id: str,
        subject_uuid: str, owner_uuid: str,
        event_log: object | None = None,
    ) -> Plan:
        """Turn a VERIFIED course-outline body into a DRAFT ``Plan`` (annual
        scope), reusing the existing ``PlanGenerator.draft`` (which records the
        ontology-coverage gaps on the drafted event). Never auto-published."""
        items: list[PlanItem] = []
        units = outline_body.get("units") if isinstance(outline_body, dict) else None
        for ui, unit in enumerate(units or []):
            for ti, topic in enumerate(unit.get("topics", []) if isinstance(unit, dict) else []):
                items.append(PlanItem(
                    item_id=f"{plan_id}.u{ui}.t{ti}",
                    title=str(topic.get("title", f"topic {ti}")) if isinstance(topic, dict) else str(topic),
                    outcomes=[OutcomeRef(str(o)) for o in (topic.get("outcomes", []) if isinstance(topic, dict) else [])],
                ))
        gen = PlanGenerator(resolve_outcome=self._resolve, event_log=event_log)
        return gen.draft(
            plan_id=plan_id, scope=PlanScope.ANNUAL,
            owner_uuid=owner_uuid, subject_uuid=subject_uuid, items=items,
        )

    # -- lesson plan --------------------------------------------------------

    def generate_lesson_plan(
        self,
        topic_id: str,
        lesson_payload: dict[str, object],
        *,
        difficulty: float | None = None,
    ) -> PlanningOutcome:
        """Generate + verify an adaptive lesson plan for a topic.

        Engagement/instructional-model awareness rides in ``lesson_payload``
        (e.g. ``instructional_model``, ``engagement``, prior performance). The
        body passes the orchestrator's confidence gate before it is returned, and
        is PREPARED as a draft — approval-routed, never auto-published.
        """
        payload = dict(lesson_payload)
        payload.setdefault("topic_id", topic_id)
        outcome, _ = self._run(CAP_LESSON, payload, difficulty=difficulty)
        return outcome

    # -- session / period plan ---------------------------------------------

    def generate_session_plan(
        self,
        lesson_plan_body: dict[str, object],
        timetable_slot: dict[str, object],
        *,
        difficulty: float | None = None,
    ) -> PlanningOutcome:
        """Generate + verify a single-period (session) plan derived from a lesson
        plan + a timetable slot. Prepared as a draft, approval-routed."""
        payload: dict[str, object] = {
            "lesson_plan": dict(lesson_plan_body),
            "timetable_slot": dict(timetable_slot),
        }
        outcome, _ = self._run(CAP_SESSION, payload, difficulty=difficulty)
        return outcome
