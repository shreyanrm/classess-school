"""Synthetic-event builders for the intelligence tests.

Import-safe and offline: builds ``EventEnvelope`` fixtures in memory, no network,
no provider. UUIDs are deterministic so projections are reproducible.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

# Make the package importable without installation (no build step is run).
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from app.models import EventEnvelope, PrerequisiteEdge, PrerequisiteGraph  # noqa: E402

# Deterministic opaque ids (no PII — random-shaped tokens).
LEARNER_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
LEARNER_B = UUID("bbbbbbbb-0000-4000-8000-000000000002")
CONSENT = UUID("cccccccc-0000-4000-8000-000000000003")

# Seed ontology topic ids (mirrors contracts/src/ontology/seed.ts).
T_EUCLID = UUID("70910000-0000-4000-8000-000000000301")
T_FUNDTHM = UUID("70910000-0000-4000-8000-000000000302")
T_IRRATIONAL = UUID("70910000-0000-4000-8000-000000000303")
T_TRIG_RATIOS = UUID("70910000-0000-4000-8000-000000000306")
T_TRIG_IDENTITIES = UUID("70910000-0000-4000-8000-000000000307")

NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)

_counter = {"n": 0}


def _next_id() -> UUID:
    _counter["n"] += 1
    return UUID(f"e0e00000-0000-4000-8000-{_counter['n']:012d}")


def attempt_event(
    *,
    subject: UUID,
    topic_id: UUID,
    mode: str,
    assistance_level: str,
    correct: bool,
    score: float | None = None,
    difficulty: float = 0.5,
    time_taken_ms: int = 30_000,
    attempt_number: int = 1,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    """Build an attempt.recorded envelope. mode/assistance coherence enforced by
    the model validator, matching the contract."""
    occurred = occurred_at or NOW
    return EventEnvelope(
        event_id=_next_id(),
        schema_version="v1",
        occurred_at=occurred,
        recorded_at=occurred,
        app="school",
        canonical_uuid=subject,
        purpose="mastery",
        consent_ref=CONSENT,
        type="attempt.recorded",
        payload={
            "attempt_id": str(_next_id()),
            "ontology": {"topic_id": str(topic_id)},
            "mode": mode,
            "assistance_level": assistance_level,
            "correct": correct,
            "score": score,
            "time_taken_ms": time_taken_ms,
            "difficulty": difficulty,
            "attempt_number": attempt_number,
        },
    )


def indep(subject: UUID, topic_id: UUID, *, correct: bool = True, **kw) -> EventEnvelope:
    """A fully-independent attempt."""
    return attempt_event(
        subject=subject, topic_id=topic_id, mode="independent",
        assistance_level="Independent", correct=correct, **kw,
    )


def supported(
    subject: UUID, topic_id: UUID, *, correct: bool = True, assistance_level: str = "Coach", **kw
) -> EventEnvelope:
    """A supported attempt at a given assistance level."""
    return attempt_event(
        subject=subject, topic_id=topic_id, mode="supported",
        assistance_level=assistance_level, correct=correct, **kw,
    )


def score_event(
    *,
    subject: UUID,
    topic_id: UUID,
    raw_score: float,
    confidence_band: str = "high",
    human_final: bool = True,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    """Build a score.recorded envelope — corroborating evidence / reassessment."""
    occurred = occurred_at or NOW
    return EventEnvelope(
        event_id=_next_id(),
        schema_version="v1",
        occurred_at=occurred,
        recorded_at=occurred,
        app="school",
        canonical_uuid=subject,
        purpose="assessment",
        consent_ref=CONSENT,
        type="score.recorded",
        payload={
            "score_id": str(_next_id()),
            "submission_id": str(_next_id()),
            "scored_subject": str(subject),
            "ontology": {"topic_id": str(topic_id)},
            "mode": "post-submission",
            "raw_score": raw_score,
            "confidence_band": confidence_band,
            "human_final": human_final,
        },
    )


@pytest.fixture
def seed_prereq_graph() -> PrerequisiteGraph:
    """Confirmed edges from the seed ontology, plus one proposed (unconfirmed)."""
    return PrerequisiteGraph(
        edges=[
            PrerequisiteEdge(from_topic_id=T_EUCLID, to_topic_id=T_FUNDTHM, kind="soft", confirmed=True, rationale="HCF via division supports prime-factorisation."),
            PrerequisiteEdge(from_topic_id=T_FUNDTHM, to_topic_id=T_IRRATIONAL, kind="hard", confirmed=True, rationale="Irrationality proofs rely on unique factorisation."),
            PrerequisiteEdge(from_topic_id=T_TRIG_RATIOS, to_topic_id=T_TRIG_IDENTITIES, kind="hard", confirmed=True, rationale="Identities are proved in terms of the basic ratios."),
            # Proposed, NOT confirmed — must never drive a routing judgment.
            PrerequisiteEdge(from_topic_id=T_IRRATIONAL, to_topic_id=T_TRIG_RATIOS, kind="soft", confirmed=False, rationale="Proposed only."),
        ]
    )


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)
