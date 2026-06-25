"""Structure / roster / policy event emission for the institution module (B1).

This module EMITS the operational events B1 owns, on the SAME attributed
envelope the spine event contract defines (contracts/src/events/envelope):

    Attribution = app . canonical_uuid . type . purpose . consent_ref

The institution module's events are operational provisioning events. The v1
spine contract's closed ``EventType`` set does not yet include structure/roster/
policy types, so these are emitted under the institution namespace
(``institution.structure.changed`` etc.) carrying the operational ``purpose``.
The envelope SHAPE is the contract's shape exactly; only the type strings and
payloads are this module's. When the spine contract adds these to its versioned
union, the type strings adopt the canonical names with no envelope change.

INVARIANTS honoured here:
  - INVARIANT 1 + 2: every envelope carries ONLY the opaque ``canonical_uuid``
    (the human who made the structural change) and opaque node / tenant ids. No
    builder accepts a name/email. A roster entry is ``canonical_uuid`` + an
    opaque role + scope — never a person's name.
  - INVARIANT 5: events are immutable + append-only. This module only APPENDS;
    there is no update or delete path.
  - INVARIANT 10: every operational payload carries the opaque ``institution_id``
    tenant scope.
  - Gateway (INVARIANT 3): every cross-service write passes the gateway. Direct
    egress is never attempted — with no gateway configured, emission DEGRADES to
    returning the built event object (the caller holds it; nothing is sent).
  - INVARIANT 8: this module holds NO credentials and constructs no auth header
    from a literal. A real sink reads its token from the environment by name.

Import-safe: stdlib only; the optional contract validation is imported lazily.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .config import InstitutionSettings, get_settings

# Purpose codes mirror contracts/src/events/primitives Purpose. Structure /
# roster / policy are institution operations.
Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]

# Institution-namespaced event types (operational). The envelope shape is the
# spine contract's; these names slot into the versioned union when added there.
STRUCTURE_CHANGED = "institution.structure.changed"
ROSTER_CHANGED = "institution.roster.changed"
POLICY_CHANGED = "institution.policy.changed"

# Canonical catalog names (12 · event catalog: institution.configured,
# membership.granted, policy.changed). These are the names the spine contract
# uses; emitted additively alongside the institution-namespaced operational
# events above. ``institution.configured`` is the one-shot "the digital twin
# exists" event the blueprint wizard emits on provisioning; ``policy.changed``
# carries the effective date + version (the versioned/effective-dated audit
# record the policy surface needs); ``membership.granted`` is the catalog name
# for a roster grant.
INSTITUTION_CONFIGURED = "institution.configured"
POLICY_CHANGED_CANONICAL = "policy.changed"
MEMBERSHIP_GRANTED = "membership.granted"

INSTITUTION_EVENT_TYPES = (
    STRUCTURE_CHANGED,
    ROSTER_CHANGED,
    POLICY_CHANGED,
    INSTITUTION_CONFIGURED,
    POLICY_CHANGED_CANONICAL,
    MEMBERSHIP_GRANTED,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Payload builders (operational; opaque ids + tenant scope; never PII)
# ---------------------------------------------------------------------------
def build_structure_payload(
    *,
    institution_id: str,
    node_id: str,
    node_kind: str,
    action: Literal["created", "updated", "moved", "archived"],
    parent_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """A structure-change payload. ``label`` is the institution's OWN display
    name for a node (data), never PII — a node is a place, not a person."""
    payload: dict[str, Any] = {
        "institution_id": institution_id,
        "node_id": node_id,
        "node_kind": node_kind,
        "action": action,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    if label is not None:
        payload["label"] = label
    return payload


def build_roster_payload(
    *,
    institution_id: str,
    node_id: str,
    member_uuid: str,
    role: str,
    action: Literal["enrolled", "assigned", "removed"],
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> dict[str, Any]:
    """A roster-change payload. The member is the OPAQUE ``canonical_uuid`` only
    (INVARIANT 1 + 2) — never a name/email. ``role`` and ``scope`` are opaque
    operational fields; role removal is immediate (action ``removed``)."""
    payload: dict[str, Any] = {
        "institution_id": institution_id,
        "node_id": node_id,
        "member_uuid": member_uuid,
        "role": role,
        "action": action,
    }
    if valid_from is not None:
        payload["valid_from"] = valid_from
    if valid_to is not None:
        payload["valid_to"] = valid_to
    return payload


def build_policy_payload(
    *,
    institution_id: str,
    node_id: str,
    key: str,
    value: Any,
    locked: bool,
    action: Literal["set", "overridden", "cleared"],
    effective_from: str | None = None,
    version: int | None = None,
) -> dict[str, Any]:
    """A policy-change payload. ``value`` is a setting (e.g. a language code),
    never PII; ``locked`` records whether it seals descendants. ``effective_from``
    (ISO date) and ``version`` carry the versioned/effective-dated audit fields so
    a consumer can reconstruct the policy timeline (spec /admin/policies:
    "versioned with effective dates + audit")."""
    payload: dict[str, Any] = {
        "institution_id": institution_id,
        "node_id": node_id,
        "key": key,
        "value": value,
        "locked": locked,
        "action": action,
    }
    if effective_from is not None:
        payload["effective_from"] = effective_from
    if version is not None:
        payload["version"] = version
    return payload


def build_configured_payload(
    *,
    institution_id: str,
    name: str,
    node_count: int,
    member_count: int,
    policy_count: int,
) -> dict[str, Any]:
    """An ``institution.configured`` payload — the one-shot "the digital twin
    exists" provisioning summary. ``name`` is the institution's OWN display name
    (data, never a person). Counts let a consumer size the twin without reading
    the structure. Carries the opaque ``institution_id`` tenant scope."""
    return {
        "institution_id": institution_id,
        "name": name,
        "node_count": node_count,
        "member_count": member_count,
        "policy_count": policy_count,
    }


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: str,
    purpose: Purpose = "operations",
    app: str = "school",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Wrap a validated payload in the attributed, append-only event envelope.

    Carries ONLY the opaque identity (the actor who made the change) — NEVER PII.
    ``event_id`` and ``recorded_at`` would be assigned by the immutable store; we
    assign provisional values for the degraded path and let the store overwrite
    them when wired.
    """
    if event_type not in INSTITUTION_EVENT_TYPES:
        raise ValueError(
            f"Unknown institution event type {event_type!r}. Known: "
            f"{', '.join(INSTITUTION_EVENT_TYPES)}."
        )
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
    """Append-only emitter for institution structure/roster/policy events.

    Every write passes the gateway (INVARIANT 3). With no gateway + sink
    configured the emitter DEGRADES to returning the built event object (the
    caller holds it; nothing is sent over the wire). It never deletes or mutates
    an event (INVARIANT 5).
    """

    def __init__(self, settings: InstitutionSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> InstitutionSettings:
        return self._settings

    @property
    def degraded(self) -> bool:
        """Degraded whenever there is no gateway-backed sink to write through."""
        return not self._settings.has_event_sink

    @property
    def sink_label(self) -> str:
        if self.degraded:
            reasons = ", ".join(self._settings.degraded_reasons())
            return f"returned-object (degraded — set: {reasons})"
        return f"gateway sink ({self._settings.gateway_url})"

    def buffered(self) -> list[dict[str, Any]]:
        """A read-only snapshot of events emitted on the degraded path."""
        return list(self._buffer)

    def emit(self, envelope: dict[str, Any]) -> EmittedEvent:
        """Emit one event.

        Degraded path: the envelope is buffered and RETURNED, reported as
        not-delivered, so callers know it is local only and nothing was sent.

        When a gateway sink is configured the real path would POST through the
        gateway (INVARIANT 3: never direct egress; the auth token is read from
        the environment by NAME, never hardcoded). That path is intentionally
        not implemented while no provider exists — the interface is the contract;
        the returned-object path is the supported path until the gateway is
        wired.
        """
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.institution.dev.gateway_url + clss.institution.dev.event_sink_url "
            "and implement the gateway POST behind this method (token read from "
            "the environment by name, never hardcoded). Until then leave them "
            "unset to use the returned-object path."
        )

    # -- convenience end-to-end emitters -----------------------------------
    def emit_structure(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        node_id: str,
        node_kind: str,
        action: Literal["created", "updated", "moved", "archived"],
        parent_id: str | None = None,
        label: str | None = None,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_structure_payload(
            institution_id=institution_id,
            node_id=node_id,
            node_kind=node_kind,
            action=action,
            parent_id=parent_id,
            label=label,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type=STRUCTURE_CHANGED,
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_roster(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        node_id: str,
        member_uuid: str,
        role: str,
        action: Literal["enrolled", "assigned", "removed"],
        valid_from: str | None = None,
        valid_to: str | None = None,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_roster_payload(
            institution_id=institution_id,
            node_id=node_id,
            member_uuid=member_uuid,
            role=role,
            action=action,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type=ROSTER_CHANGED,
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_policy(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        node_id: str,
        key: str,
        value: Any,
        locked: bool,
        action: Literal["set", "overridden", "cleared"],
        effective_from: str | None = None,
        version: int | None = None,
        event_type: str = POLICY_CHANGED,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        """Emit a policy-change event. Defaults to the institution-namespaced
        ``institution.policy.changed``; pass ``event_type=POLICY_CHANGED_CANONICAL``
        for the catalog name. ``effective_from``/``version`` carry the
        versioned/effective-dated audit fields."""
        payload = build_policy_payload(
            institution_id=institution_id,
            node_id=node_id,
            key=key,
            value=value,
            locked=locked,
            action=action,
            effective_from=effective_from,
            version=version,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type=event_type,
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_configured(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        name: str,
        node_count: int,
        member_count: int,
        policy_count: int,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        """Emit the one-shot ``institution.configured`` provisioning event."""
        payload = build_configured_payload(
            institution_id=institution_id,
            name=name,
            node_count=node_count,
            member_count=member_count,
            policy_count=policy_count,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type=INSTITUTION_CONFIGURED,
            occurred_at=occurred_at,
        )
        return self.emit(envelope)
