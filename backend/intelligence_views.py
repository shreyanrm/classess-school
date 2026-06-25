"""The governed INTELLIGENCE READ — the spine's one-engine, one-truth faucet.

This is the live HTTP read service the web surface's gateway-first intelligence
reads hit. It serves the four governed views the spine owns — learner mastery,
gaps, recommendations, class insights — computed by REPLAYING the immutable
event store through the ONE engine (``spine/intelligence``). The web NEVER
re-implements this; its in-browser ``lib/engine.ts`` is only a degrade fallback.

The engine is pure + deterministic: same events -> same views. With no event
provider wired (``clss.intelligence.dev.database_url`` unset) the engine reads
the in-memory degraded source — here, a small PII-free scenario seed keyed by
opaque canonical refs only — so the faucet answers identically with or without a
DB. Wiring a real gateway-backed event source later changes nothing here.

CONFIDENTIALITY: every id is an opaque canonical ref. No PII, no names, no board
lock-in, no real pricing. The seed mirrors the web's neutral Class 10-B scenario
(generic Student A..H) so the gateway view and the fallback view agree.

LAW: import-safe; degrade cleanly. If the engine package cannot load, the views
service reports unavailable and the door falls back (the wall still admitted the
read; the surface degrades to its in-browser port) — the deployable never breaks.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from . import loader

logger = logging.getLogger("clss.backend.intelligence")

_INTEL_ALIAS = "clss_svc_intelligence"

# Load the ONE engine under its own alias (same pattern as the spine services).
# Degrades to None if absent/broken — the door then falls back cleanly.
_engine = loader.load_package(_INTEL_ALIAS, "spine/intelligence/app")
if _engine is None:  # pragma: no cover - defensive degrade path
    logger.warning("intelligence engine unavailable; governed reads will degrade")


# --------------------------------------------------------------------------- #
# The scenario seed — a deterministic, PII-free event set the in-memory engine
# replays when no DB is wired. Opaque canonical refs only; generic labels live in
# the surface, never here. Mirrors the web's loopData scenario so the gateway
# view and the in-browser fallback agree (one truth).
# --------------------------------------------------------------------------- #
# Stable opaque refs (the web's ROSTER uses the same Student A/B tokens).
_STUDENT_A = uuid.UUID("a0000000-0000-4000-8000-00000000000a")
_STUDENT_B = uuid.UUID("a0000000-0000-4000-8000-00000000000b")
# Stable opaque topic ref (deterministic, not derived from any real ontology id).
_TOPIC = uuid.UUID("70000000-0000-4000-8000-000000000001")
# A fixed "now" so the seeded projection is reproducible across runs.
_SCENARIO_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _attempt(
    subject: uuid.UUID,
    *,
    correct: bool,
    mode: str,
    level: str,
    score: float,
    when: datetime,
    time_ms: int = 25_000,
) -> Any:
    return _engine.EventEnvelope(
        event_id=uuid.uuid4(),
        occurred_at=when,
        recorded_at=when,
        app="learner",
        canonical_uuid=subject,
        purpose="assessment",
        consent_ref=uuid.uuid4(),
        type="attempt.recorded",
        payload={
            "attempt_id": str(uuid.uuid4()),
            "ontology": {"topic_id": str(_TOPIC)},
            "mode": mode,
            "assistance_level": level,
            "correct": correct,
            "score": score,
            "time_taken_ms": time_ms,
            "difficulty": 0.5,
        },
    )


def _seed_events() -> list[Any]:
    """A small mix of independent + supported work for two learners — enough for
    the engine to derive a real mastery band and a confirmed gap. Deterministic."""
    t0 = _SCENARIO_NOW - timedelta(days=2)
    t1 = _SCENARIO_NOW - timedelta(days=1)
    return [
        # Student A — mostly independent, secure-ish.
        _attempt(_STUDENT_A, correct=True, mode="independent", level="Independent", score=0.92, when=t0),
        _attempt(_STUDENT_A, correct=True, mode="independent", level="Independent", score=0.88, when=t1),
        # Student B — supported + weak: a confirmable gap signal.
        _attempt(_STUDENT_B, correct=False, mode="supported", level="Hint", score=0.30, when=t0),
        _attempt(_STUDENT_B, correct=False, mode="supported", level="Coach", score=0.35, when=t1),
    ]


# --------------------------------------------------------------------------- #
# The REAL event source — replay the persisted event store through the ONE
# engine when configured; degrade to the PII-free seed (observably) when not.
#
# The engine owns the source seam (``spine/intelligence/app/source.py``):
# ``make_event_source`` returns the LIVE gateway-backed ``GatewayEventSource``
# when ``clss.intelligence.dev.database_url`` (+ gateway url/token) are set, and
# the in-memory degraded source otherwise — reading every secret by NAME from
# the environment, never a literal. We pass ``events=_seed_events()`` so that
# the degraded in-memory source replays the SAME deterministic scenario the web
# fallback uses (one truth), while a configured deploy reads the persisted events
# the web surface wrote to ``platform.events`` THROUGH the gateway.
# --------------------------------------------------------------------------- #
# The web persists ``platform.events`` keyed by ``CLSS_DATABASE_URL``; the engine
# names its own ``CLSS_INTELLIGENCE_DEV_DATABASE_URL``. Honour BOTH as the event
# source selector: if the intelligence-specific name is unset but the shared one
# is present, treat the source as configured (read by NAME, value never logged).
_SHARED_DB_ENV = "CLSS_DATABASE_URL"


def _build_settings() -> Any:
    """The engine settings with the shared ``CLSS_DATABASE_URL`` honoured as a
    fallback event-source selector. Returns None if the engine is unavailable."""
    if _engine is None:  # pragma: no cover - defensive
        return None
    settings = _engine.get_settings()
    if not settings.database_url:
        shared = os.environ.get(_SHARED_DB_ENV)
        if shared and shared.strip():
            # Re-derive settings with the shared DB url as the source selector.
            # PRESENCE selects the live source; the gateway url/token still gate
            # the actual read (fail-safe, no fabricated events without them).
            settings = settings.model_copy(update={"database_url": shared})
    return settings


def _source_and_events(subject: Optional[uuid.UUID]) -> tuple[Any, list[Any], dict[str, Any]]:
    """Resolve the active event source, the events to replay, and an OBSERVABLE
    provenance marker. When a live source is configured we replay the PERSISTED
    events; otherwise we replay the seed and mark the result ``degraded``."""
    settings = _build_settings()
    if settings is None:  # pragma: no cover - defensive
        return None, _seed_events(), {"source": "seed", "degraded": True, "backend": "engine-unavailable"}

    source = _engine.make_event_source(settings, events=_seed_events())
    live = bool(getattr(settings, "has_event_source", False))
    if not live:
        return source, _seed_events(), {
            "source": "seed",
            "degraded": True,
            "backend": source.backend,
            "degraded_reasons": settings.degraded_reasons(),
        }

    events = source.read_events(subject=subject)
    meta: dict[str, Any] = {"source": "live", "degraded": False, "backend": source.backend}
    if not events:
        # Configured but the gateway returned nothing (no token / unreachable /
        # empty): degrade to the seed OBSERVABLY rather than show an empty,
        # never-mistaken-for-live view.
        logger.warning("intelligence: live source configured but returned no events; degrading to seed")
        events = _seed_events()
        meta = {
            "source": "seed",
            "degraded": True,
            "backend": source.backend,
            "degraded_reasons": settings.degraded_reasons() or ["live source returned no events"],
        }
    return source, events, meta


# The provenance of the most recent read, so the HTTP faucet can surface it on a
# response header (list views — gaps/recommendations — cannot carry an inline
# marker, so the header is the observable seam for them).
_last_source_meta: dict[str, Any] = {"source": "unknown", "degraded": True}


def last_source_meta() -> dict[str, Any]:
    """The provenance (source/degraded/backend) of the most recent ``read``."""
    return dict(_last_source_meta)


# --------------------------------------------------------------------------- #
# View serialisation — plain JSON-able dicts. Plain-language only for humans; the
# raw composite is included for ranking (the surface never shows it raw).
# --------------------------------------------------------------------------- #
def _mastery_view(proj: Any) -> dict[str, Any]:
    r = proj.mastery.reading
    return {
        "topic_id": str(proj.topic_id),
        "reading": {
            "dimensions": r.dimensions.model_dump(),
            "composite": r.composite,
            "band": r.band,
            "independent": r.independent,
        },
        # camelCase mirror so the web's shape guard (isMasteryShape) trusts it.
        "plainLanguage": proj.plain_language,
        "plain_language": proj.plain_language,
        "observation_count": proj.mastery.observation_count,
    }


def _gap_view(g: Any) -> dict[str, Any]:
    return {
        "gap_type": g.gap_type,
        "confidence": g.evidence.confidence,
        "confirmed": g.confirmed,
        "rationale": g.evidence.rationale,
        "signal_count": g.signal_count,
    }


# A fixed namespace so an engine-derived recommendation gets a DETERMINISTIC,
# STABLE id: the same confirmed gap on the same topic always yields the same
# recommendation_id, across requests and across process restarts. This is the
# keystone of durability (GAP#2) — the id the web surfaces from a recommend can
# be approved/executed later because it can be RE-DERIVED (and the rec rehydrated)
# from the same engine replay, never depending on transient process state.
_REC_NAMESPACE = uuid.UUID("5eed0000-0000-4000-8000-0000000000c1")


def recommendation_id_for(topic_id: str, gap_type: str) -> str:
    """The stable, engine-derived recommendation id for a (topic, gap) pair."""
    return str(uuid.uuid5(_REC_NAMESPACE, f"{topic_id}|{gap_type}"))


def _recommendation_view(graph: Any) -> list[dict[str, Any]]:
    """Proactive recommendations derived from the cohort's confirmed gaps. Each is
    a RECOMMEND-level item (the lowest permission rung) with a STABLE,
    engine-derived ``recommendation_id`` so recommend -> approve -> execute all
    reference the SAME object; acting on it is gated by the ladder, never here."""
    recs: list[dict[str, Any]] = []
    for topic_id in sorted(graph.topic_ids(), key=str):
        summary = graph.topic_summary(topic_id)
        for gap_type, count in sorted(summary.confirmed_gap_counts.items()):
            recs.append(
                {
                    "recommendation_id": recommendation_id_for(str(topic_id), gap_type),
                    "topic_id": str(topic_id),
                    "gap_type": gap_type,
                    "learner_count": count,
                    "kind": "intervention",
                    "ladder": "recommend",
                }
            )
    return recs


def recommendations() -> list[dict[str, Any]]:
    """The engine-derived recommendation feed (the SAME source the governed
    ``recommendations`` view serves), or an empty list when the engine is
    unavailable. Each item carries the stable ``recommendation_id``."""
    if _engine is None:
        return []
    _, events, _ = _source_and_events(None)
    graph = _engine.build_learner_graph(events, asof=_SCENARIO_NOW)
    return _recommendation_view(graph)


def recommendation_by_id(recommendation_id: str) -> Optional[dict[str, Any]]:
    """Resolve ONE engine-derived recommendation by its stable id, re-derived from
    the same engine replay. Returns the view dict, or None if the id is not a
    current engine recommendation. This is the durability seam: an id can always
    be re-resolved from the engine, never only from transient process state."""
    rid = str(recommendation_id or "").strip()
    for rec in recommendations():
        if rec.get("recommendation_id") == rid:
            return rec
    return None


def _class_insights_view(graph: Any) -> dict[str, Any]:
    """The teacher's rolled-up class intelligence view: per-topic band distribution
    and the learners (opaque refs) needing attention."""
    reads: list[dict[str, Any]] = []
    band_totals: dict[str, int] = {}
    needing: list[dict[str, Any]] = []
    for subject, profile in graph.profiles.items():
        for topic_id, proj in profile.topics.items():
            band = proj.mastery.reading.band
            band_totals[band] = band_totals.get(band, 0) + 1
            entry = {
                "subject_uuid": str(subject),
                "topic_id": str(topic_id),
                "band": band,
                "plainLanguage": proj.plain_language,
                "confirmed_gaps": [g.gap_type for g in proj.confirmed_gaps],
            }
            reads.append(entry)
            if proj.confirmed_gaps or band in ("not-started", "emerging", "developing"):
                needing.append(entry)
    return {
        "summary": {"band_counts": band_totals, "learner_count": len(graph.profiles)},
        "needingAttention": needing,
        "reads": reads,
    }


# --------------------------------------------------------------------------- #
# The faucet — dispatch a governed read to the right view. Returns a JSON-able
# body, or None when the view is unknown (the door then returns the generic ack).
# --------------------------------------------------------------------------- #
class IntelligenceUnavailable(RuntimeError):
    """Raised when the engine package could not be loaded (degrade -> fallback)."""


def available() -> bool:
    return _engine is not None


def read(*, view: Optional[str], subject_uuid: Optional[str]) -> Any:
    """Compute one governed view by replaying the event store through the ONE
    engine. ``view`` is the dotted view selector the web sends:

      ``mastery:<topic_id>`` / ``gaps:<topic_id>`` -> learner views (subject scoped)
      ``recommendations``                          -> proactive recommendation list
      ``class-insights``                           -> the teacher's class roll-up

    Returns the view body (JSON-able). Raises ``IntelligenceUnavailable`` if the
    engine is absent so the caller falls back; raises ``ValueError`` for an
    unknown/malformed view so the caller returns the generic admitted ack.
    """
    if _engine is None:  # pragma: no cover - defensive
        raise IntelligenceUnavailable("intelligence engine not loaded")

    asof = _SCENARIO_NOW
    selector = (view or "").strip()

    if selector.startswith("mastery:") or selector.startswith("gaps:"):
        kind, _, topic_raw = selector.partition(":")
        if not subject_uuid or not topic_raw:
            raise ValueError("learner view requires subject_uuid + topic")
        subject = uuid.UUID(subject_uuid)
        topic = uuid.UUID(topic_raw)
        _, events, meta = _source_and_events(subject)
        _last_source_meta.clear()
        _last_source_meta.update(meta)
        proj = _engine.build_topic_projection(events, subject=subject, topic_id=topic, asof=asof)
        if kind == "mastery":
            body = _mastery_view(proj)
            body["_meta"] = meta  # dict view -> inline observable provenance
            return body
        # Gaps is a bare list (the web's shape guard checks Array.isArray); it
        # cannot carry an inline marker — the faucet surfaces meta on a header.
        return [_gap_view(g) for g in proj.gaps]

    if selector == "recommendations":
        _, events, meta = _source_and_events(None)
        _last_source_meta.clear()
        _last_source_meta.update(meta)
        graph = _engine.build_learner_graph(events, asof=asof)
        return _recommendation_view(graph)

    if selector == "class-insights":
        _, events, meta = _source_and_events(None)
        _last_source_meta.clear()
        _last_source_meta.update(meta)
        graph = _engine.build_learner_graph(events, asof=asof)
        body = _class_insights_view(graph)
        body["_meta"] = meta  # dict view -> inline observable provenance
        return body

    raise ValueError(f"unknown intelligence view: {selector!r}")
