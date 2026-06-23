"""``profile.updated`` event emission for the personalization module.

This module EMITS one event family — ``profile.updated`` — along the same
attributed, append-only envelope as the v1 contract (contracts/src/events/*).
Each event records that a learner's PROVISIONAL personalization profile was
re-derived from fresh signal: which trait kinds are now held, each with its
confidence and evidence lineage, and which kinds the consent/age-tier gate
denied. The platform improves across every event (the proactive loop) while the
profile itself stays provisional.

INVARIANTS honoured here:

  - INVARIANT 1 + 2: the event carries ONLY the opaque ``canonical_uuid`` and
    opaque ids (trait values are opaque/enumerated, evidence ids are opaque event
    refs). No PII — the builder asserts no name/email/dob key is present.
  - INVARIANT 5: events are immutable + append-only. A profile update is a NEW
    event capturing the new provisional read, never an in-place mutation. A
    revocation that clears traits is itself emitted as a profile.updated with the
    reduced trait set.
  - INVARIANT 6: every event is stamped with the consent_ref under which it was
    captured and the ``account`` purpose (personalization profiling is a
    consent-lifecycle-adjacent, account-scoped activity).
  - INVARIANT 3 + 8: every write passes the gateway; the module holds no
    credentials. With no gateway configured, emission degrades to a clearly
    labelled in-memory append-only sink and the auth token is NEVER hardcoded.

Import-safe and offline: no network, no DB, no secret value read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from .config import PersonalizationSettings, get_settings
from .infer import InferredTrait
from .profile import PersonalizationProfile

Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]

PersonalizationEventType = Literal["profile.updated"]

# Keys that would indicate PII leaked into a payload — asserted absent.
_PII_HINT_KEYS = ("name", "email", "phone", "dob", "address", "fullname", "username")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


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


def _assert_pii_free(payload: dict[str, Any]) -> None:
    blob = " ".join(str(k).lower() for k in _flatten_keys(payload))
    for hint in _PII_HINT_KEYS:
        if hint in blob:
            raise ValueError(
                f"Event payload appears to carry PII (key contains '{hint}'). "
                "Personalization events carry ONLY opaque ids and behavioral data."
            )


def _trait_summary(trait: InferredTrait) -> dict[str, Any]:
    """A single trait as it appears on the wire — provisional, evidenced,
    confident, explainable. The value is opaque/enumerated; the evidence ids are
    opaque event refs. No raw human text about a person."""
    return {
        "kind": trait.kind.value,
        "value": trait.value,
        "confidence": round(trait.confidence, 4),
        "provisional": True,  # never a permanent label
        "evidence_signal_ids": list(trait.evidence_signal_ids),
        "explanation": trait.explanation,
    }


def build_profile_updated_payload(
    profile: PersonalizationProfile,
    *,
    trigger: Literal["fresh-signal", "revocation", "consent-change"] = "fresh-signal",
) -> dict[str, Any]:
    """Build a ``profile.updated`` payload from a projected profile.

    Captures the full provisional read: every held trait with its confidence and
    evidence lineage, plus the kinds the consent/age-tier gate denied (for
    transparency). ``trigger`` records WHY the profile changed (fresh signal, a
    revocation that cleared traits, or a consent change).
    """
    payload: dict[str, Any] = {
        "trait_kinds": sorted({t.kind.value for t in profile.traits}),
        "traits": [_trait_summary(t) for t in profile.traits],
        "denied_trait_kinds": [k for k, _ in profile.denied_traits],
        "trigger": trigger,
        "provisional": True,
        "source_signal_ids": list(profile.source_signal_ids),
    }
    _assert_pii_free(payload)
    return payload


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: PersonalizationEventType = "profile.updated",
    purpose: Purpose = "account",
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


class PersonalizationEventEmitter:
    """Append-only emitter for ``profile.updated`` events.

    Every write passes the gateway (INVARIANT 3). With no gateway + sink
    configured the emitter degrades to an in-memory append-only buffer, clearly
    labelled, so the deterministic flow works offline and tests stay green. It
    never deletes or mutates a buffered event (INVARIANT 5).
    """

    def __init__(self, settings: PersonalizationSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> PersonalizationSettings:
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
        gateway (token read from the environment by name, never hardcoded); that
        path is intentionally not implemented while no provider exists."""
        _assert_pii_free(envelope.get("payload", {}))
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.personalization.dev.gateway_url + "
            "clss.personalization.dev.gateway_token + "
            "clss.personalization.dev.event_sink_url and implement the gateway "
            "POST behind this method (token read from the environment by name, "
            "never hardcoded). Until then leave them unset to use the in-memory "
            "append-only sink."
        )

    def emit_profile_updated(
        self,
        profile: PersonalizationProfile,
        *,
        consent_ref: str,
        trigger: Literal["fresh-signal", "revocation", "consent-change"] = "fresh-signal",
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        """Build and emit a ``profile.updated`` event for a projected profile."""
        payload = build_profile_updated_payload(profile, trigger=trigger)
        envelope = build_envelope(
            canonical_uuid=profile.subject,
            consent_ref=consent_ref,
            payload=payload,
            occurred_at=occurred_at,
        )
        return self.emit(envelope)


__all__ = [
    "Purpose",
    "PersonalizationEventType",
    "build_profile_updated_payload",
    "build_envelope",
    "EmittedEvent",
    "PersonalizationEventEmitter",
]
