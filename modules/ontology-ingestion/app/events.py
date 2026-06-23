"""Event emission for Curriculum & ontology ingestion (A2).

This module EMITS the operational events A2 owns as its ingestion pipeline runs.
These are NOT learner behavioural events — they record ontology lifecycle facts
(opaque ids only, no PII, ever):

  - ``ontology.node_ingested``       — a curriculum node was mapped into the
                                       graph as a DRAFT from a source document.
  - ``ontology.edge_proposed``       — the steward PROPOSED a prerequisite edge
                                       (``confirmed = False``; not yet trusted).
  - ``ontology.edge_confirmed``      — a human steward CONFIRMED a proposed edge.
                                       Carries the opaque ``confirmed_by`` ref;
                                       refuses to fire without one.
  - ``ontology.equivalence_mapped``  — a cross-board equivalence was recorded.

INVARIANTS honoured here:
  - Behavioural data carries ONLY the opaque canonical_uuid; these ontology
    events likewise carry ONLY opaque ids (node/edge/steward refs, board CODE
    labels). No builder accepts a name/email. No PII, ever.
  - Events are immutable + append-only. This module only APPENDS; it never
    updates or deletes. The envelope has no mutation path.
  - PERMISSION LADDER: an ``edge_confirmed`` event is only built with a
    ``confirmed_by`` ref present — confirming a prerequisite edge is a
    consequential, expert act; the emitter refuses to fabricate confirmation.
  - Every cross-service write passes the gateway. With no gateway + sink
    configured, emission degrades to a clearly-labelled in-memory append-only
    sink. Direct egress is never attempted.

Envelope shape mirrors contracts/src/events/envelope.ts: attribution
(app · canonical_uuid · purpose · consent_ref) + occurred_at + a typed body.
A2's operational events use ``purpose = "operations"`` and ride the SAME
attributed, append-only envelope so the store, gateway, and audit treat them
identically.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .config import OntologySettings, get_settings

Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]

OntologyEventType = Literal[
    "ontology.node_ingested",
    "ontology.edge_proposed",
    "ontology.edge_confirmed",
    "ontology.equivalence_mapped",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: OntologyEventType,
    purpose: Purpose = "operations",
    app: str = "school",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Wrap a payload in the attributed, append-only event envelope.

    Attribution = app . canonical_uuid . type . purpose . consent_ref
    (contracts/src/events/envelope). Carries ONLY opaque ids — NEVER PII.
    ``canonical_uuid`` here is the opaque ref of the steward/operator acting on
    the ontology (a system or human actor), never a learner's identity. The
    immutable store assigns final ``event_id`` / ``recorded_at``; we assign
    provisional values for the degraded in-memory path.
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


# ---------------------------------------------------------------------------
# Payload builders (opaque ids only)
# ---------------------------------------------------------------------------


def build_node_ingested_payload(
    *,
    node_id: str,
    node_kind: str,
    board_code: str,
    source_ref: str,
    draft: bool = True,
    extraction_confidence: float | None = None,
) -> dict[str, Any]:
    """Payload for ``ontology.node_ingested`` — a node mapped from a source.

    ``draft`` is ``True``: ingestion never publishes a node as trusted. The
    board is a CODE label, not a baked-in enum. ``source_ref`` is an opaque
    document handle, never the document's contents.
    """
    payload: dict[str, Any] = {
        "node_id": node_id,
        "node_kind": node_kind,
        "board_code": board_code,
        "source_ref": source_ref,
        "draft": bool(draft),
    }
    if extraction_confidence is not None:
        payload["extraction_confidence"] = round(float(extraction_confidence), 4)
    return payload


def build_edge_proposed_payload(
    *,
    edge_id: str,
    from_topic_id: str,
    to_topic_id: str,
    kind: str,
    rationale: str,
    confidence: float,
) -> dict[str, Any]:
    """Payload for ``ontology.edge_proposed`` — a PROPOSED prerequisite edge.

    Always records ``confirmed = False``: a proposed edge is never trusted for
    routing until a steward confirms it. Carries the rationale for
    explainability and the steward's confidence in the proposal.
    """
    return {
        "edge_id": edge_id,
        "from_topic_id": from_topic_id,
        "to_topic_id": to_topic_id,
        "kind": kind,
        "confirmed": False,
        "rationale": rationale,
        "confidence": round(float(confidence), 4),
    }


def build_edge_confirmed_payload(
    *,
    edge_id: str,
    from_topic_id: str,
    to_topic_id: str,
    confirmed_by: str,
    decision: Literal["confirmed", "rejected"] = "confirmed",
) -> dict[str, Any]:
    """Payload for ``ontology.edge_confirmed`` — a steward's DECISION on a
    proposed edge.

    Refuses to build without ``confirmed_by`` (an opaque human steward ref):
    confirming a prerequisite edge is consequential and never auto-fires
    (PERMISSION LADDER). The emitter never fabricates a confirmation. A
    rejection is recorded the same way (append-only), with ``decision`` set.
    """
    if not confirmed_by:
        raise PermissionError(
            "ontology.edge_confirmed records a consequential expert decision "
            "and requires a confirmed_by steward ref. A prerequisite edge is "
            "never auto-confirmed."
        )
    return {
        "edge_id": edge_id,
        "from_topic_id": from_topic_id,
        "to_topic_id": to_topic_id,
        "decision": decision,
        "confirmed": decision == "confirmed",
        "confirmed_by": confirmed_by,
    }


def build_equivalence_mapped_payload(
    *,
    equivalence_id: str,
    node_id: str,
    node_kind: str,
    equivalent_board_code: str,
    equivalent_label: str,
    confidence: float,
    equivalent_node_id: str | None = None,
) -> dict[str, Any]:
    """Payload for ``ontology.equivalence_mapped`` — a cross-board mapping.

    Both boards are CODE labels (board-agnostic). Carries the confidence so a
    consumer can gate on it.
    """
    payload: dict[str, Any] = {
        "equivalence_id": equivalence_id,
        "node_id": node_id,
        "node_kind": node_kind,
        "equivalent_board_code": equivalent_board_code,
        "equivalent_label": equivalent_label,
        "confidence": round(float(confidence), 4),
    }
    if equivalent_node_id is not None:
        payload["equivalent_node_id"] = equivalent_node_id
    return payload


@dataclass
class EmittedEvent:
    """An event handed to the emitter, with its delivery status."""

    envelope: dict[str, Any]
    delivered: bool  # True only when accepted by a real sink through the gateway.
    sink: str  # human-readable sink label (degraded or gateway).


class EventEmitter:
    """Append-only emitter for A2 ontology lifecycle events.

    Every write passes the gateway (INVARIANT). With no gateway + sink
    configured it degrades to an in-memory append-only buffer, clearly labelled,
    so the deterministic flow works offline and tests stay green. It never
    deletes or mutates a buffered event — append-only in spirit and in code.
    """

    def __init__(self, settings: OntologySettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> OntologySettings:
        return self._settings

    @property
    def degraded(self) -> bool:
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
        environment by NAME, never hardcoded). That path is intentionally not
        implemented while no provider exists — the EventEmitter interface is the
        contract; the in-memory path is the supported path until the gateway is
        wired.
        """
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.ontology.dev.gateway_url + clss.ontology.dev.event_sink_url "
            "and implement the gateway POST behind this method (token read from "
            "the environment by NAME, never hardcoded). Until then leave them "
            "unset to use the in-memory append-only sink."
        )

    # -- convenience end-to-end emitters -----------------------------------

    def emit_node_ingested(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        node_id: str,
        node_kind: str,
        board_code: str,
        source_ref: str,
        draft: bool = True,
        extraction_confidence: float | None = None,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_node_ingested_payload(
            node_id=node_id,
            node_kind=node_kind,
            board_code=board_code,
            source_ref=source_ref,
            draft=draft,
            extraction_confidence=extraction_confidence,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="ontology.node_ingested",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_edge_proposed(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        edge_id: str,
        from_topic_id: str,
        to_topic_id: str,
        kind: str,
        rationale: str,
        confidence: float,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_edge_proposed_payload(
            edge_id=edge_id,
            from_topic_id=from_topic_id,
            to_topic_id=to_topic_id,
            kind=kind,
            rationale=rationale,
            confidence=confidence,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="ontology.edge_proposed",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_edge_confirmed(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        edge_id: str,
        from_topic_id: str,
        to_topic_id: str,
        confirmed_by: str,
        decision: Literal["confirmed", "rejected"] = "confirmed",
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_edge_confirmed_payload(
            edge_id=edge_id,
            from_topic_id=from_topic_id,
            to_topic_id=to_topic_id,
            confirmed_by=confirmed_by,
            decision=decision,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="ontology.edge_confirmed",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_equivalence_mapped(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        equivalence_id: str,
        node_id: str,
        node_kind: str,
        equivalent_board_code: str,
        equivalent_label: str,
        confidence: float,
        equivalent_node_id: str | None = None,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_equivalence_mapped_payload(
            equivalence_id=equivalence_id,
            node_id=node_id,
            node_kind=node_kind,
            equivalent_board_code=equivalent_board_code,
            equivalent_label=equivalent_label,
            confidence=confidence,
            equivalent_node_id=equivalent_node_id,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="ontology.equivalence_mapped",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)
