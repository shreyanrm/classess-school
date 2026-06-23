"""Evidence event emission for the Learning module (B7).

This module EMITS the events the rest of the platform treats as evidence:

  - ``attempt.recorded`` — one learner attempt, carrying the keystone
    independent-vs-supported ``mode`` and the assistance ``assistance_level``
    actually used (the raw material for the Independence dimension and the
    support-dependency gap).
  - a practice "mastery-evidence" attempt — the same ``attempt.recorded`` shape;
    practice contributes EVIDENCE, not a completion tick, so a practice item is
    an attempt event keyed to the ontology node, never a "done" flag.

INVARIANTS honoured here:
  - INVARIANT 1 + 2: every event carries ONLY the opaque ``canonical_uuid`` and
    opaque ontology ids. No PII, ever. The builders accept no name/email field.
  - INVARIANT 5: events are immutable + append-only. This module only APPENDS;
    it never updates or deletes. The contract envelope has no mutation path.
  - Gateway: every cross-service write passes the gateway (INVARIANT). Direct
    egress is never attempted — with no gateway configured, emission degrades to
    a clearly-labelled in-memory append-only sink.
  - INVARIANT 8: this module holds NO credentials and constructs no auth header
    from a literal. A real sink reads its token from the environment by name.

The Learning module does NOT author mastery. ``mastery.updated`` is owned by the
intelligence engine / event store (CORE). What this module contributes is the
attempt EVIDENCE the mastery model reads; a convenience builder
:func:`build_mastery_evidence_attempt` makes the "this attempt is mastery
evidence" intent explicit while still emitting the canonical attempt shape.

Import-safe: the pydantic-backed contract models are imported lazily inside the
builders, so importing this module never requires the dependency. When pydantic
is unavailable the builders fall back to constructing/validating plain dicts so
the deterministic path still works offline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .config import LearningSettings, get_settings
from .ladder import attempt_mode_of

AttemptMode = Literal["independent", "supported"]
Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _validate_attempt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an attempt payload against the contract shape when the engine's
    pydantic mirror is importable; otherwise enforce the load-bearing coherence
    rules by hand so a malformed event is never produced even offline.

    The single most important check: mode 'independent' <-> assistance_level
    'Independent' (the attempt contract's superRefine). We never let an
    incoherent attempt through, with or without pydantic.
    """
    try:  # Prefer the authoritative contract mirror in the spine engine.
        from spine.intelligence.app.models import AttemptPayload  # type: ignore

        return AttemptPayload.model_validate(payload).model_dump(mode="json")
    except Exception:
        pass

    # Deterministic offline fallback: enforce the coherence the contract enforces.
    mode = payload.get("mode")
    level = payload.get("assistance_level")
    is_independent_level = level == "Independent"
    if mode == "independent" and not is_independent_level:
        raise ValueError("mode 'independent' requires assistance_level 'Independent'.")
    if mode == "supported" and is_independent_level:
        raise ValueError("mode 'supported' cannot use assistance_level 'Independent'.")
    score = payload.get("score")
    if score is not None and not (0.0 <= float(score) <= 1.0):
        raise ValueError("score must be in [0,1].")
    diff = payload.get("difficulty")
    if diff is None or not (0.0 <= float(diff) <= 1.0):
        raise ValueError("difficulty is required and must be in [0,1].")
    if int(payload.get("time_taken_ms", 0)) < 0:
        raise ValueError("time_taken_ms must be non-negative.")
    return dict(payload)


def build_attempt_payload(
    *,
    topic_id: str,
    assistance_level: str,
    correct: bool,
    difficulty: float,
    time_taken_ms: int,
    score: float | None = None,
    question_id: str | None = None,
    outcome_id: str | None = None,
    competency_id: str | None = None,
    skill_id: str | None = None,
    attempt_number: int = 1,
    mode: AttemptMode | None = None,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    """Build a validated ``AttemptPayload`` dict (contracts/src/events/attempt).

    The ``mode`` is DERIVED from the assistance level unless given, so the
    keystone independent-vs-supported flag is always coherent with the rung the
    learner actually used. The independent-vs-supported flag is the single most
    important bit in the evidence layer — it is never guessed away from the rung.
    """
    derived_mode = mode if mode is not None else attempt_mode_of(assistance_level)
    ontology: dict[str, Any] = {"topic_id": topic_id}
    if outcome_id:
        ontology["outcome_id"] = outcome_id
    if competency_id:
        ontology["competency_id"] = competency_id
    if skill_id:
        ontology["skill_id"] = skill_id

    payload: dict[str, Any] = {
        "attempt_id": attempt_id or _new_uuid(),
        "ontology": ontology,
        "mode": derived_mode,
        "assistance_level": assistance_level,
        "correct": correct,
        "score": score,
        "time_taken_ms": int(time_taken_ms),
        "difficulty": float(difficulty),
        "attempt_number": int(attempt_number),
    }
    if question_id:
        payload["question_id"] = question_id
    return _validate_attempt_payload(payload)


def build_mastery_evidence_attempt(
    *,
    topic_id: str,
    assistance_level: str,
    correct: bool,
    difficulty: float,
    time_taken_ms: int,
    score: float | None = None,
    question_id: str | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    """A practice attempt framed as MASTERY EVIDENCE.

    Practice contributes evidence, not a completion tick — so a practice item is
    emitted as an ``attempt.recorded`` event keyed to the ontology node, carrying
    the assistance level and the derived independent-vs-supported flag. There is
    no "completed" boolean anywhere in this builder by design.
    """
    return build_attempt_payload(
        topic_id=topic_id,
        assistance_level=assistance_level,
        correct=correct,
        difficulty=difficulty,
        time_taken_ms=time_taken_ms,
        score=score,
        question_id=question_id,
        attempt_number=attempt_number,
        # purpose is set on the envelope; the attempt shape itself is identical.
    )


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: str = "attempt.recorded",
    purpose: Purpose = "mastery",
    app: str = "school",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Wrap a validated payload in the attributed, append-only event envelope.

    Attribution = app . canonical_uuid . type . purpose . consent_ref
    (contracts/src/events/envelope). Carries ONLY the opaque identity — NEVER
    PII. ``event_id`` and ``recorded_at`` would be assigned by the immutable
    store; we assign provisional values for the degraded in-memory path and let
    the store overwrite them when wired.
    """
    occurred = occurred_at or _now_iso()
    return {
        "event_id": _new_uuid(),
        "schema_version": "v1",
        "occurred_at": occurred,
        "recorded_at": occurred,
        "app": app,
        "canonical_uuid": canonical_uuid,
        "purpose": purpose,
        "consent_ref": consent_ref,
        "type": event_type,
        "payload": payload,
    }


@dataclass
class EmittedEvent:
    """An event handed to the emitter, with its delivery status."""

    envelope: dict[str, Any]
    delivered: bool  # True only when accepted by a real sink through the gateway.
    sink: str  # human-readable sink label (degraded or gateway).


class EventEmitter:
    """Append-only emitter for evidence events.

    Every write passes the gateway (INVARIANT). With no gateway + sink
    configured the emitter degrades to an in-memory append-only buffer, clearly
    labelled, so the deterministic flow works offline and tests stay green. It
    never deletes or mutates a buffered event — append-only in spirit and in
    code (INVARIANT 5).
    """

    def __init__(self, settings: LearningSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> LearningSettings:
        return self._settings

    @property
    def degraded(self) -> bool:
        """Degraded whenever there is no gateway-backed sink to write through."""
        return not self._settings.has_event_sink

    @property
    def sink_label(self) -> str:
        if self.degraded:
            reasons = ", ".join(self._settings.degraded_reasons())
            return f"in-memory (degraded — set: {reasons})"
        return f"gateway sink ({self._settings.gateway_url})"

    def buffered(self) -> list[dict[str, Any]]:
        """A read-only snapshot of the append-only buffer (degraded path)."""
        return list(self._buffer)

    def emit(self, envelope: dict[str, Any]) -> EmittedEvent:
        """Emit one event. In the degraded path it is appended to the in-memory
        buffer and reported as not-delivered (so callers know it is local only).

        When a gateway sink is configured the real path would POST through the
        gateway (INVARIANT: never direct egress; the auth token is read from the
        environment by name, never hardcoded). That path is intentionally not
        implemented while no provider exists — the EventEmitter interface is the
        contract; the in-memory path is the supported path until the gateway is
        wired.
        """
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.learning.dev.gateway_url + clss.learning.dev.event_sink_url and "
            "implement the gateway POST behind this method (token read from the "
            "environment by name, never hardcoded). Until then leave them unset "
            "to use the in-memory append-only sink."
        )

    def emit_attempt(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        topic_id: str,
        assistance_level: str,
        correct: bool,
        difficulty: float,
        time_taken_ms: int,
        score: float | None = None,
        question_id: str | None = None,
        attempt_number: int = 1,
        purpose: Purpose = "mastery",
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        """Build + emit one ``attempt.recorded`` evidence event end to end."""
        payload = build_attempt_payload(
            topic_id=topic_id,
            assistance_level=assistance_level,
            correct=correct,
            difficulty=difficulty,
            time_taken_ms=time_taken_ms,
            score=score,
            question_id=question_id,
            attempt_number=attempt_number,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="attempt.recorded",
            purpose=purpose,
            occurred_at=occurred_at,
        )
        return self.emit(envelope)
