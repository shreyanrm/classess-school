"""The governed READ VIEW + the engine's EVENT EMISSION — the live circuit wiring.

This is the boundary the rest of the system touches. The engine derives mastery
and gaps by replaying events (``profile.py``); this module turns one learner's
projection into:

  1. the GOVERNED READ VIEW — the stable, PII-free, plain-language, evidence-linked
     shape a surface reads through the gateway (``POST /v1/intelligence/read``,
     mapped in ``spine/gateway/app/routing.py`` for ``learning.read`` /
     ``intelligence-views.read``). It is the ONE truth: independent-vs-supported
     mastery and a NAMED gap, each in plain language, each linked to the source
     events. Surfaces read this gateway-first and fall back to the in-browser TS
     engine ONLY on a degraded wall. The composite number and the raw formula are
     NEVER in the view (a guard enforces it).

  2. the EVENTS the engine emits as a consequence of a recompute —
     ``mastery.updated``, ``gap.detected``, ``gap.resolved`` — each attributed,
     consent-stamped, evidence-linked, and append-only. The engine NEVER authors
     mastery as state; it emits the derived conclusion as an event so the loop and
     the rest of the spine can react. Emission passes the gateway; with no sink
     configured it degrades to an in-memory append-only buffer (the derivation is
     unaffected — events are the only thing written, and only as a projection).

INVARIANTS honoured here:
  - 1 + 2: keyed by the opaque ``canonical_uuid`` and opaque ontology ids only;
    no PII. The plain-language guard also rejects any digit/percent/formula in a
    learner-facing string, so the scalar can never leak through the view.
  - 5: events are immutable + append-only; a resolve is a NEW event, never a
    mutation.
  - 6: every emitted event carries the ``consent_ref`` it was derived under and a
    ``purpose``; a view read is for a stated purpose.
  - 3 + 8: emission passes the gateway; the engine holds NO credential (the token
    is read from the environment by name only, never hardcoded).

Pure + deterministic for the view; emission is the only side effect and degrades
to an in-memory sink offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from .config import IntelligenceSettings, get_settings
from .gaps import GapResult
from .mastery import MasteryResult
from .models import EventEnvelope, MasteryWeights, PrerequisiteGraph, now_utc
from .profile import LearnerProfile, TopicProjection, build_profile

# Purpose under which a governed intelligence read is legitimate. Mirrors the
# event ``Purpose`` literal; a read is for one of these.
ReadPurpose = Literal["instruction", "assessment", "mastery", "intervention"]

# Independence is the keystone read the surface foregrounds. "independent" =
# demonstrated alone; "support-dependent" = only with help; "not-started" = no
# evidence yet. Everything short of independent is, by definition, still
# support-dependent — exactly the distinction the Independence dimension exists
# to surface.
IndependenceState = Literal["independent", "support-dependent", "not-started"]


def _independence_state(mastery: MasteryResult) -> IndependenceState:
    if mastery.observation_count == 0:
        return "not-started"
    if mastery.reading.independent:
        return "independent"
    return "support-dependent"


# A learner-facing string must carry NO number, percentage, or formula — that
# would leak the mastery scalar. Mirrors the guard in the learner-record module
# so the same rule holds on both sides of the gateway.
_FORBIDDEN_CHARS = set("0123456789%=^")


def assert_no_scalar(text: str) -> str:
    """Guard: a plain-language string must not leak a number/percent/formula.
    Returns the text unchanged when clean; raises otherwise."""
    if any(ch in _FORBIDDEN_CHARS for ch in text) or "×" in text or " x " in text:
        raise ValueError(
            f"plain-language text leaks a scalar (number/percent/formula): {text!r}"
        )
    return text


# ---------------------------------------------------------------------------
# The governed read view — the stable shape the gateway returns.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GapView:
    """One named gap, ready for a surface: the type, the plain-language 'what to
    do', whether it is confirmed, its confidence, and its evidence lineage."""

    gap_type: str
    plain_language: str
    confirmed: bool
    confidence: float
    evidence_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.evidence_event_ids:
            raise ValueError("a gap view must link to its evidence events.")


@dataclass(frozen=True)
class TopicReadView:
    """One topic on the governed read view. Carries the plain-language band, the
    keystone independence state, the named gaps, and the evidence lineage —
    NEVER the composite number or the formula (the guard enforces it)."""

    topic_id: str
    band: str
    plain_language: str
    independence: IndependenceState
    gaps: tuple[GapView, ...]
    source_event_ids: tuple[str, ...]
    last_evidence_at: datetime | None
    observation_count: int

    def __post_init__(self) -> None:
        assert_no_scalar(self.plain_language)


@dataclass(frozen=True)
class LearnerReadView:
    """The full governed read view for one learner — what a surface renders.

    Keyed by the opaque ``canonical_uuid`` only. ``degraded_reasons`` names (never
    values) the env vars whose absence kept the engine degraded, so a surface can
    show the fall-back-to-local-engine affordance."""

    subject: str
    purpose: ReadPurpose
    topics: tuple[TopicReadView, ...]
    computed_at: datetime
    degraded_reasons: tuple[str, ...] = ()

    def topic(self, topic_id: str) -> TopicReadView | None:
        for t in self.topics:
            if t.topic_id == topic_id:
                return t
        return None

    @property
    def support_dependent_topics(self) -> tuple[TopicReadView, ...]:
        return tuple(t for t in self.topics if t.independence == "support-dependent")


def _gap_view(g: GapResult) -> GapView:
    return GapView(
        gap_type=g.gap_type,
        # The rationale is already plain-language "what to do"; it may legitimately
        # be empty only if a rule produced none, which never happens. It carries
        # no scalar by construction (the rules write words, not numbers).
        plain_language=g.evidence.rationale,
        confirmed=g.confirmed,
        confidence=g.evidence.confidence,
        evidence_event_ids=tuple(str(i) for i in g.evidence.evidence_event_ids),
    )


def _topic_read_view(proj: TopicProjection) -> TopicReadView:
    return TopicReadView(
        topic_id=str(proj.topic_id),
        band=proj.mastery.reading.band,
        plain_language=proj.mastery.plain_language,
        independence=_independence_state(proj.mastery),
        gaps=tuple(_gap_view(g) for g in proj.gaps),
        source_event_ids=tuple(str(i) for i in proj.mastery.evidence_event_ids),
        last_evidence_at=proj.last_evidence_at,
        observation_count=proj.mastery.observation_count,
    )


def view_from_profile(
    profile: LearnerProfile,
    *,
    purpose: ReadPurpose = "mastery",
) -> LearnerReadView:
    """Render an already-built (PII-free) profile into the governed read view.

    Deterministic: same profile -> same view. Topics are ordered by their opaque
    id for a stable, diff-friendly payload."""
    topics = tuple(
        _topic_read_view(profile.topics[tid])
        for tid in sorted(profile.topics, key=str)
    )
    return LearnerReadView(
        subject=str(profile.subject),
        purpose=purpose,
        topics=topics,
        computed_at=profile.computed_at,
        degraded_reasons=tuple(profile.degraded_reasons),
    )


def read_view(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    purpose: ReadPurpose = "mastery",
    graph: PrerequisiteGraph | None = None,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
    degraded_reasons: list[str] | None = None,
) -> LearnerReadView:
    """The entry point ``POST /v1/intelligence/read`` calls: replay -> profile ->
    governed read view. The ONE source of truth a surface reads gateway-first.

    The events handed in are assumed already consent + purpose gated by the event
    store's governed read (this engine adds no identity beyond the opaque token).
    """
    profile = build_profile(
        events, subject=subject, graph=graph, weights=weights, asof=asof,
        degraded_reasons=degraded_reasons,
    )
    return view_from_profile(profile, purpose=purpose)


# ---------------------------------------------------------------------------
# Event emission — the engine emits its derived conclusions as events.
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return now_utc().isoformat()


def build_mastery_updated_payload(view: TopicReadView) -> dict[str, Any]:
    """``mastery.updated`` payload: the plain-language band + independence state +
    lineage. No composite number (the guard already rejected one in the view)."""
    return {
        "ontology": {"topic_id": view.topic_id},
        "band": view.band,
        "plain_language": view.plain_language,
        "independence": view.independence,
        "observation_count": view.observation_count,
        "source_event_ids": list(view.source_event_ids),
    }


def build_gap_payload(view: TopicReadView, gap: GapView) -> dict[str, Any]:
    """``gap.detected`` / ``gap.resolved`` payload: the NAMED gap, plain-language,
    confirmation, confidence, and evidence lineage."""
    return {
        "ontology": {"topic_id": view.topic_id},
        "gap_type": gap.gap_type,
        "plain_language": gap.plain_language,
        "confirmed": gap.confirmed,
        "confidence": gap.confidence,
        "source_event_ids": list(gap.evidence_event_ids),
    }


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: str,
    purpose: str = "mastery",
    app: str = "school",
) -> dict[str, Any]:
    """Wrap a payload in the attributed, append-only event envelope.

    Attribution = app . canonical_uuid . type . purpose . consent_ref. Carries
    ONLY the opaque identity. ``event_id`` / ``recorded_at`` are provisional in the
    degraded path; the immutable store assigns authoritative values when wired."""
    occurred = _now_iso()
    return {
        "event_id": str(uuid4()),
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
    envelope: dict[str, Any]
    delivered: bool  # True only when accepted by a real sink through the gateway.
    sink: str


class IntelligenceEmitter:
    """Append-only emitter for the engine's derived-state events.

    Every write passes the gateway (INVARIANT 3); the engine holds no credential
    (INVARIANT 8 — the token is read from the environment by name only). With no
    sink configured it degrades to an in-memory append-only buffer (INVARIANT 5 —
    never mutated), so the deterministic flow works offline and tests stay green.
    """

    def __init__(self, settings: IntelligenceSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def degraded(self) -> bool:
        return not self._settings.has_event_sink

    @property
    def sink_label(self) -> str:
        if self.degraded:
            return (
                "in-memory (degraded — set clss.intelligence.dev.gateway_url + "
                ".gateway_token + .event_sink_url)"
            )
        return f"gateway sink ({self._settings.event_sink_url})"

    def buffered(self) -> list[dict[str, Any]]:
        return list(self._buffer)

    def emit(self, envelope: dict[str, Any]) -> EmittedEvent:
        """Emit one event. Degraded -> append to the buffer, report not-delivered.
        Wired -> POST through the gateway (token read from the environment by name,
        never hardcoded); that path is intentionally not implemented while no
        provider exists, mirroring the source/sink degrade pattern elsewhere."""
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.intelligence.dev.gateway_url + .gateway_token + .event_sink_url "
            "and implement the gateway POST behind this method (token read from "
            "the environment by name, never hardcoded). Until then leave them "
            "unset to use the in-memory append-only sink."
        )

    def emit_for_view(
        self,
        view: LearnerReadView,
        *,
        consent_ref: str,
        previous: LearnerReadView | None = None,
    ) -> list[EmittedEvent]:
        """Emit the events implied by a (re)computed read view.

        For every topic: a ``mastery.updated`` (the band moved or first read), a
        ``gap.detected`` for each CONFIRMED gap, and a ``gap.resolved`` for any gap
        that was confirmed in ``previous`` but is gone now. Unconfirmed gaps are
        NEVER emitted as detected — they are prompts-to-reassess, not judgments.

        Idempotent against ``previous``: with no change, nothing is emitted (the
        engine emits a conclusion only when the conclusion changed)."""
        out: list[EmittedEvent] = []
        for t in view.topics:
            prev_t = previous.topic(t.topic_id) if previous is not None else None
            # mastery.updated — only when the band changed (or first observation).
            if prev_t is None or prev_t.band != t.band:
                out.append(self.emit(build_envelope(
                    canonical_uuid=view.subject,
                    consent_ref=consent_ref,
                    payload=build_mastery_updated_payload(t),
                    event_type="mastery.updated",
                    purpose=view.purpose,
                )))
            confirmed_now = {g.gap_type for g in t.gaps if g.confirmed}
            confirmed_before = (
                {g.gap_type for g in prev_t.gaps if g.confirmed} if prev_t else set()
            )
            # gap.detected — newly confirmed gaps only.
            for g in t.gaps:
                if g.confirmed and g.gap_type not in confirmed_before:
                    out.append(self.emit(build_envelope(
                        canonical_uuid=view.subject,
                        consent_ref=consent_ref,
                        payload=build_gap_payload(t, g),
                        event_type="gap.detected",
                        purpose=view.purpose,
                    )))
            # gap.resolved — was confirmed before, no longer confirmed now.
            for gone in sorted(confirmed_before - confirmed_now):
                prev_gap = next(g for g in prev_t.gaps if g.gap_type == gone)  # type: ignore[union-attr]
                out.append(self.emit(build_envelope(
                    canonical_uuid=view.subject,
                    consent_ref=consent_ref,
                    payload=build_gap_payload(t, prev_gap),
                    event_type="gap.resolved",
                    purpose=view.purpose,
                )))
        return out


__all__ = [
    "ReadPurpose",
    "IndependenceState",
    "assert_no_scalar",
    "GapView",
    "TopicReadView",
    "LearnerReadView",
    "view_from_profile",
    "read_view",
    "build_mastery_updated_payload",
    "build_gap_payload",
    "build_envelope",
    "EmittedEvent",
    "IntelligenceEmitter",
]
