"""Portfolio / credential event emission for the Learner-record module (B8).

B8 EMITS two families of events (the only things it writes):

  - ``portfolio.artifact_added`` — a learner curated an artifact into their
    portfolio (with provenance).
  - ``portfolio.artifact_featured`` — a learner featured / unfeatured an
    artifact.
  - ``credential.issued`` — a verifiable credential was issued.
  - ``credential.revoked`` — the learner withdrew a credential.

These extend the v1 event family (contracts/src/events/*) along the same
attributed, append-only envelope. B8 does NOT emit attempt/score/mastery events
— those are CORE evidence it READS, never authors.

INVARIANTS honoured here:
  - INVARIANT 1 + 2: every event carries ONLY the opaque ``canonical_uuid`` and
    opaque ids (artifact/credential/topic). No PII — the builders accept no
    name/email field and the envelope asserts none is present.
  - INVARIANT 5: events are immutable + append-only. This module only APPENDS;
    a "feature" or "revoke" is a NEW event, never an in-place mutation.
  - INVARIANT 6: every event is stamped with the consent_ref under which it was
    captured and a purpose (``mastery`` for the learner record).
  - INVARIANT 3 + 8: every write passes the gateway; the module holds no
    credentials. With no gateway configured, emission degrades to a clearly
    labelled in-memory append-only sink and the auth token is NEVER hardcoded.

Import-safe and offline: no network, no DB, no secret value read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .config import LearnerRecordSettings, get_settings

Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]

# The B8-owned event types (extend the v1 family along the same envelope).
LearnerRecordEventType = Literal[
    "portfolio.artifact_added",
    "portfolio.artifact_featured",
    "credential.issued",
    "credential.revoked",
]

# Keys that would indicate PII leaked into a payload — asserted absent.
_PII_HINT_KEYS = ("name", "email", "phone", "dob", "address")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _assert_pii_free(payload: dict[str, Any]) -> None:
    blob = " ".join(str(k).lower() for k in _flatten_keys(payload))
    for hint in _PII_HINT_KEYS:
        if hint in blob:
            raise ValueError(
                f"Event payload appears to carry PII (key contains '{hint}'). "
                "B8 events carry ONLY opaque ids and behavioral data."
            )


def _flatten_keys(obj: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(str(k))
            keys.extend(_flatten_keys(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            keys.extend(_flatten_keys(v))
    return keys


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def build_artifact_added_payload(
    *,
    artifact_id: str,
    topic_id: str,
    source_event_ids: list[str],
    produced_mode: Literal["independent", "supported"],
    content_ref: str,
    title: str,
) -> dict[str, Any]:
    """Build a ``portfolio.artifact_added`` payload. Provenance is required —
    an artifact event without source events is refused."""
    if not source_event_ids:
        raise ValueError("artifact_added requires provenance source_event_ids.")
    payload = {
        "artifact_id": artifact_id,
        "ontology": {"topic_id": topic_id},
        "source_event_ids": list(source_event_ids),
        "produced_mode": produced_mode,
        "content_ref": content_ref,
        "title": title,
    }
    _assert_pii_free(payload)
    return payload


def build_artifact_featured_payload(
    *,
    artifact_id: str,
    featured: bool,
) -> dict[str, Any]:
    """Build a ``portfolio.artifact_featured`` payload (append-only toggle)."""
    payload = {"artifact_id": artifact_id, "featured": bool(featured)}
    _assert_pii_free(payload)
    return payload


def build_credential_issued_payload(
    *,
    credential_id: str,
    topic_id: str,
    claim_kind: str,
    statement: str,
    source_event_ids: list[str],
    verifiable: bool,
) -> dict[str, Any]:
    """Build a ``credential.issued`` payload. Evidence-linked and PII-free."""
    if not source_event_ids:
        raise ValueError("credential.issued requires evidence source_event_ids.")
    if any(ch.isdigit() for ch in statement) or "%" in statement:
        raise ValueError("credential statement must be plain language (no number/percentage).")
    payload = {
        "credential_id": credential_id,
        "ontology": {"topic_id": topic_id},
        "claim_kind": claim_kind,
        "statement": statement,
        "source_event_ids": list(source_event_ids),
        "verifiable": bool(verifiable),
    }
    _assert_pii_free(payload)
    return payload


def build_credential_revoked_payload(
    *,
    credential_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build a ``credential.revoked`` payload (learner withdrawing control)."""
    payload: dict[str, Any] = {"credential_id": credential_id}
    if reason:
        payload["reason"] = reason
    _assert_pii_free(payload)
    return payload


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: LearnerRecordEventType,
    purpose: Purpose = "mastery",
    app: str = "school",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Wrap a validated payload in the attributed, append-only event envelope.

    Attribution = app . canonical_uuid . type . purpose . consent_ref
    (contracts/src/events/envelope). Carries ONLY the opaque identity — NEVER
    PII. ``event_id`` and ``recorded_at`` are provisional for the degraded path;
    the immutable store assigns the authoritative values when wired.
    """
    _assert_pii_free(payload)
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
    sink: str        # human-readable sink label (degraded or gateway).


class EventEmitter:
    """Append-only emitter for portfolio/credential events.

    Every write passes the gateway (INVARIANT 3). With no gateway + sink
    configured the emitter degrades to an in-memory append-only buffer, clearly
    labelled, so the deterministic flow works offline and tests stay green. It
    never deletes or mutates a buffered event (INVARIANT 5).
    """

    def __init__(self, settings: LearnerRecordSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> LearnerRecordSettings:
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
        """Emit one event. Degraded -> append to the in-memory buffer and report
        not-delivered. With a gateway sink wired the real path POSTs through the
        gateway (token read from the environment by name, never hardcoded);
        that path is intentionally not implemented while no provider exists."""
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.learner-record.dev.gateway_url + "
            "clss.learner-record.dev.gateway_token + "
            "clss.learner-record.dev.event_sink_url and implement the gateway "
            "POST behind this method (token read from the environment by name, "
            "never hardcoded). Until then leave them unset to use the in-memory "
            "append-only sink."
        )

    # Convenience end-to-end emitters --------------------------------------

    def emit_artifact_added(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        artifact_id: str,
        topic_id: str,
        source_event_ids: list[str],
        produced_mode: Literal["independent", "supported"],
        content_ref: str,
        title: str,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_artifact_added_payload(
            artifact_id=artifact_id,
            topic_id=topic_id,
            source_event_ids=source_event_ids,
            produced_mode=produced_mode,
            content_ref=content_ref,
            title=title,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="portfolio.artifact_added",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_credential_issued(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        credential_id: str,
        topic_id: str,
        claim_kind: str,
        statement: str,
        source_event_ids: list[str],
        verifiable: bool,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_credential_issued_payload(
            credential_id=credential_id,
            topic_id=topic_id,
            claim_kind=claim_kind,
            statement=statement,
            source_event_ids=source_event_ids,
            verifiable=verifiable,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="credential.issued",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)


__all__ = [
    "Purpose",
    "LearnerRecordEventType",
    "build_artifact_added_payload",
    "build_artifact_featured_payload",
    "build_credential_issued_payload",
    "build_credential_revoked_payload",
    "build_envelope",
    "EmittedEvent",
    "EventEmitter",
]
