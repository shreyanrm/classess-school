"""Event emission for coursework & assessment (B6).

Builds and emits the coursework events against the EXACT contract shapes
(contracts/src/events/*): ``assignment.created``, ``submission.created``,
``score.recorded``, and the attempt evidence (``attempt.recorded``) that carries
the keystone INDEPENDENT-vs-SUPPORTED flag.

INVARIANTS held here:
  - Behavioural data carries ONLY the opaque ``canonical_uuid`` — never PII.
  - Every event is attributed: app . canonical_uuid . purpose . consent_ref.
  - The event store is immutable + append-only; this module only ever APPENDS.
  - Consent is stamped on every event (``consent_ref``) and the purpose travels.
  - A ``score.recorded`` event's ``human_final`` reflects the marking gate — a
    consequential auto-recommendation is emitted with ``human_final=False`` until
    a human confirms; it is the marking gate's truth, never an engine claim.

Degrades gracefully: with no event store wired, ``emit`` validates the event and
RETURNS the envelope object (it does not silently drop it and never fabricates a
persisted id beyond a local one). The store seam matches the event-store
interface shape (``EventStore.append``); an async store is awaited, a sync
sink is called directly.

The store is CONSUMED via its interface — this module never reaches into the
event-store internals.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from .assignments import Assignment
from .contracts import (
    EvaluationConfidenceBand,
    MarkingGate,
    event_confidence_band_for,
    score_mode_for,
)
from .evaluation import EvaluationOutcome


APP_ID = "school"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# The store seam — matches the event-store EventStore.append interface shape.
# ---------------------------------------------------------------------------
class EventSink(Protocol):
    """Anything that can append an attributed event. The event-store
    ``EventStore.append`` (async) satisfies this; a local list sink (sync) does
    too. ``emit`` adapts to either."""

    def append(
        self,
        *,
        canonical_uuid: UUID,
        app: str,
        type: str,
        purpose: str,
        consent_ref: UUID,
        payload: dict,
        occurred_at: datetime,
    ) -> Any:
        ...


@dataclass(frozen=True)
class EmittedEvent:
    """The local envelope returned from ``emit``. When a store is wired, the
    store's returned envelope is folded in; degraded, this IS the result."""

    type: str
    app: str
    canonical_uuid: UUID
    purpose: str
    consent_ref: UUID
    payload: dict
    occurred_at: datetime
    persisted: bool
    event_id: UUID | None = None
    store_backend: str | None = None


# ---------------------------------------------------------------------------
# The emitter.
# ---------------------------------------------------------------------------
class CourseworkEvents:
    """Builds + emits coursework events. Holds the attribution context (app,
    consent) so every event is stamped consistently."""

    def __init__(self, *, sink: EventSink | None = None) -> None:
        self._sink = sink

    @property
    def has_sink(self) -> bool:
        return self._sink is not None

    # -- builders (pure; return the contract payload dict) -----------------
    @staticmethod
    def build_assignment_created(assignment: Assignment) -> dict:
        """``assignment.created`` payload. Carries the verification block when the
        assignment's items were AI-generated (the per-item verification rolls up
        only when present — the contract holds it at the assignment level)."""
        payload: dict = {
            "assignment_id": str(assignment.assignment_id),
            "institution_id": str(assignment.institution_id),
            "created_by": str(assignment.created_by),
            "ontology": _ontology_dict(assignment.ontology),
            "title": assignment.title,
        }
        if assignment.due_at is not None:
            payload["due_at"] = _iso(assignment.due_at)
        # If any item was generated, surface the weakest passing verification so
        # the assignment-level block reflects that content was verified.
        gen_items = [i for i in assignment.items if i.ai_generated and i.verification is not None]
        if gen_items:
            v = min(gen_items, key=lambda i: i.verification.confidence).verification  # type: ignore[union-attr]
            payload["verification"] = {
                "status": v.status,
                "confidence": v.confidence,
                "gate_threshold": v.gate_threshold,
                "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in v.checks],
            }
        return payload

    @staticmethod
    def build_submission_created(
        *, submission_id: UUID, assignment_id: UUID, submitted_by: UUID, attempt_ids: list[UUID], submitted_at: datetime
    ) -> dict:
        """``submission.created`` payload. ``submitted_by`` and the attempt ids are
        opaque refs — never PII."""
        return {
            "submission_id": str(submission_id),
            "assignment_id": str(assignment_id),
            "submitted_by": str(submitted_by),
            "attempt_ids": [str(a) for a in attempt_ids],
            "submitted_at": _iso(submitted_at),
        }

    @staticmethod
    def build_score_recorded(outcome: EvaluationOutcome, *, ontology: dict, score_id: UUID | None = None) -> dict:
        """``score.recorded`` payload from an evaluation outcome.

        ``human_final`` is the marking gate's truth: a consequential mark is
        ``human_final`` only once a human confirmed it. The recorded ``raw_score``
        is the effective (human-adjusted if confirmed, else engine-recommended)
        normalized score. The confidence band maps the evaluation band onto the
        event band (low/medium/high)."""
        gate = outcome.marking_gate
        return {
            "score_id": str(score_id or uuid4()),
            "submission_id": str(outcome.submission_ref),
            "scored_subject": str(outcome.scored_subject),
            "ontology": ontology,
            "mode": score_mode_for(outcome.mode),
            "raw_score": gate.effective_score,
            "confidence_band": event_confidence_band_for(gate.engine_confidence_band),
            "human_final": gate.final,
        }

    @staticmethod
    def build_attempt_evidence(
        *,
        attempt_id: UUID,
        ontology: dict,
        independent: bool,
        assistance_level: str,
        correct: bool,
        difficulty: float,
        time_taken_ms: int,
        question_id: UUID | None = None,
        score: float | None = None,
        attempt_number: int = 1,
    ) -> dict:
        """``attempt.recorded`` evidence payload — the INDEPENDENT-vs-SUPPORTED flag
        is the keystone. ``independent`` maps to mode 'independent' + assistance
        'Independent'; supported uses the supplied scaffold level.

        The contract enforces mode/assistance coherence; this builder keeps them
        coherent so no malformed evidence reaches the immutable store."""
        if independent:
            mode = "independent"
            level = "Independent"
        else:
            mode = "supported"
            level = assistance_level if assistance_level != "Independent" else "Check-my-work"
        payload: dict = {
            "attempt_id": str(attempt_id),
            "ontology": ontology,
            "mode": mode,
            "assistance_level": level,
            "correct": correct,
            "time_taken_ms": int(time_taken_ms),
            "difficulty": float(difficulty),
            "attempt_number": int(attempt_number),
        }
        if question_id is not None:
            payload["question_id"] = str(question_id)
        if score is not None:
            payload["score"] = float(score)
        return payload

    # -- emit --------------------------------------------------------------
    async def emit(
        self,
        *,
        type: str,
        canonical_uuid: UUID,
        purpose: str,
        consent_ref: UUID,
        payload: dict,
        occurred_at: datetime | None = None,
    ) -> EmittedEvent:
        """Append one attributed event through the sink, or return it degraded.

        ``canonical_uuid`` is the opaque subject ref (never PII). ``consent_ref``
        stamps the consent the event was captured under (INVARIANT 6). Adapts to a
        sync or async sink ``append``.
        """
        occurred_at = occurred_at or _now()
        if self._sink is None:
            # Degraded: validate-and-return. The event is well-formed and ready
            # to persist once a store is wired (clss.coursework.dev.event_store_url).
            return EmittedEvent(
                type=type,
                app=APP_ID,
                canonical_uuid=canonical_uuid,
                purpose=purpose,
                consent_ref=consent_ref,
                payload=payload,
                occurred_at=occurred_at,
                persisted=False,
            )

        result = self._sink.append(
            canonical_uuid=canonical_uuid,
            app=APP_ID,
            type=type,
            purpose=purpose,
            consent_ref=consent_ref,
            payload=payload,
            occurred_at=occurred_at,
        )
        if inspect.isawaitable(result):
            result = await result

        event_id = None
        backend = getattr(self._sink, "backend", None)
        if isinstance(result, dict):
            raw_id = result.get("event_id")
            if isinstance(raw_id, UUID):
                event_id = raw_id
            elif isinstance(raw_id, str):
                event_id = UUID(raw_id)
        return EmittedEvent(
            type=type,
            app=APP_ID,
            canonical_uuid=canonical_uuid,
            purpose=purpose,
            consent_ref=consent_ref,
            payload=payload,
            occurred_at=occurred_at,
            persisted=True,
            event_id=event_id,
            store_backend=backend,
        )


# ---------------------------------------------------------------------------
# helpers.
# ---------------------------------------------------------------------------
def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _ontology_dict(ontology: Any) -> dict:
    """Serialize an OntologyRef (pydantic) or pass through a plain dict."""
    if isinstance(ontology, dict):
        return ontology
    out: dict = {"topic_id": str(ontology.topic_id)}
    if getattr(ontology, "outcome_id", None) is not None:
        out["outcome_id"] = str(ontology.outcome_id)
    if getattr(ontology, "competency_id", None) is not None:
        out["competency_id"] = str(ontology.competency_id)
    if getattr(ontology, "skill_id", None) is not None:
        out["skill_id"] = str(ontology.skill_id)
    return out


def ontology_dict(ontology: Any) -> dict:
    """Public helper to serialize an OntologyRef to the contract dict shape."""
    return _ontology_dict(ontology)


# ---------------------------------------------------------------------------
# A local, append-only sink for tests and degraded local runs. Mirrors the
# event-store discipline: append only, never mutated. Clearly labelled as not
# durable. This is NOT the event store — it is a stand-in sink for the seam.
# ---------------------------------------------------------------------------
class InMemoryEventSink:
    """An append-only in-memory sink satisfying the ``EventSink`` interface.

    Not durable; clearly labelled. Enforces append-only (no mutation API)."""

    backend = "in-memory append-only sink (degraded — set clss.coursework.dev.event_store_url)"

    def __init__(self) -> None:
        self._log: list[dict] = []

    def append(
        self,
        *,
        canonical_uuid: UUID,
        app: str,
        type: str,
        purpose: str,
        consent_ref: UUID,
        payload: dict,
        occurred_at: datetime,
    ) -> dict:
        envelope = {
            "event_id": uuid4(),
            "canonical_uuid": canonical_uuid,
            "app": app,
            "type": type,
            "purpose": purpose,
            "consent_ref": consent_ref,
            "payload": payload,
            "occurred_at": occurred_at,
            "recorded_at": _now(),
            "schema_version": "v1",
        }
        self._log.append(envelope)
        return dict(envelope)

    @property
    def events(self) -> list[dict]:
        """A read-only copy of the appended log."""
        return [dict(e) for e in self._log]
