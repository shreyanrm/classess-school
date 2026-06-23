"""Synthetic-event builders for the feature-store tests.

Import-safe and offline: builds intelligence ``EventEnvelope`` fixtures in
memory, no network, no provider, no DB. UUIDs are deterministic so projections
and predictions are reproducible. Mirrors the intelligence engine's own test
conftest so the two suites speak the same event language.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

# Make the feature-store package importable without installation (no build step).
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# The feature store binds the engine via its interop shim; importing it here
# both proves the shim resolves and gives the tests the engine event model.
from app.intelligence_interop import (  # noqa: E402
    EventEnvelope,
    PrerequisiteEdge,
    PrerequisiteGraph,
)

# Deterministic opaque ids (no PII — random-shaped tokens).
LEARNER_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
LEARNER_B = UUID("bbbbbbbb-0000-4000-8000-000000000002")
CONSENT = UUID("cccccccc-0000-4000-8000-000000000003")

# Seed ontology topic ids (mirror the engine seed / contracts seed).
T_EUCLID = UUID("70910000-0000-4000-8000-000000000301")
T_FUNDTHM = UUID("70910000-0000-4000-8000-000000000302")
T_IRRATIONAL = UUID("70910000-0000-4000-8000-000000000303")
T_TRIG_RATIOS = UUID("70910000-0000-4000-8000-000000000306")
T_TRIG_IDENTITIES = UUID("70910000-0000-4000-8000-000000000307")

NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)


class _Ids:
    """Deterministic id generator, resettable per test for reproducibility."""

    def __init__(self) -> None:
        self.n = 0

    def reset(self) -> None:
        self.n = 0

    def next(self) -> UUID:
        self.n += 1
        return UUID(f"e0e00000-0000-4000-8000-{self.n:012d}")


_IDS = _Ids()


@pytest.fixture(autouse=True)
def _reset_ids() -> None:
    """Reset the id counter before every test so event ids are reproducible
    regardless of test order."""
    _IDS.reset()


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
    occurred = occurred_at or NOW
    return EventEnvelope(
        event_id=_IDS.next(),
        schema_version="v1",
        occurred_at=occurred,
        recorded_at=occurred,
        app="school",
        canonical_uuid=subject,
        purpose="mastery",
        consent_ref=CONSENT,
        type="attempt.recorded",
        payload={
            "attempt_id": str(_IDS.next()),
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
    return attempt_event(
        subject=subject, topic_id=topic_id, mode="independent",
        assistance_level="Independent", correct=correct, **kw,
    )


def supported(
    subject: UUID, topic_id: UUID, *, correct: bool = True, assistance_level: str = "Coach", **kw
) -> EventEnvelope:
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
    occurred = occurred_at or NOW
    return EventEnvelope(
        event_id=_IDS.next(),
        schema_version="v1",
        occurred_at=occurred,
        recorded_at=occurred,
        app="school",
        canonical_uuid=subject,
        purpose="assessment",
        consent_ref=CONSENT,
        type="score.recorded",
        payload={
            "score_id": str(_IDS.next()),
            "submission_id": str(_IDS.next()),
            "scored_subject": str(subject),
            "ontology": {"topic_id": str(topic_id)},
            "mode": "post-submission",
            "raw_score": raw_score,
            "confidence_band": confidence_band,
            "human_final": human_final,
        },
    )


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


@pytest.fixture
def seed_prereq_graph() -> PrerequisiteGraph:
    return PrerequisiteGraph(
        edges=[
            PrerequisiteEdge(from_topic_id=T_EUCLID, to_topic_id=T_FUNDTHM, kind="soft", confirmed=True, rationale="HCF via division supports prime-factorisation."),
            PrerequisiteEdge(from_topic_id=T_FUNDTHM, to_topic_id=T_IRRATIONAL, kind="hard", confirmed=True, rationale="Irrationality proofs rely on unique factorisation."),
            PrerequisiteEdge(from_topic_id=T_IRRATIONAL, to_topic_id=T_TRIG_RATIOS, kind="soft", confirmed=False, rationale="Proposed only."),
        ]
    )


@pytest.fixture
def improving_history() -> list[EventEnvelope]:
    """A learner climbing: supported early, independent and succeeding later, all
    fresh. Should read as improving trajectory and rising readiness."""
    return [
        supported(LEARNER_A, T_FUNDTHM, correct=False, score=0.3, occurred_at=days_ago(20)),
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=0.6, assistance_level="Hint", occurred_at=days_ago(14)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.8, occurred_at=days_ago(7)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.9, difficulty=0.7, occurred_at=days_ago(2)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, difficulty=0.7, occurred_at=days_ago(1)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, difficulty=0.8, occurred_at=NOW),
    ]


@pytest.fixture
def declining_history() -> list[EventEnvelope]:
    """A learner slipping: strong early independent work, then a recent drop.
    Should read as declining/elevated risk."""
    return [
        indep(LEARNER_B, T_TRIG_RATIOS, correct=True, score=0.9, occurred_at=days_ago(20)),
        indep(LEARNER_B, T_TRIG_RATIOS, correct=True, score=0.8, occurred_at=days_ago(14)),
        indep(LEARNER_B, T_TRIG_RATIOS, correct=False, score=0.4, occurred_at=days_ago(6)),
        indep(LEARNER_B, T_TRIG_RATIOS, correct=False, score=0.2, occurred_at=days_ago(2)),
        indep(LEARNER_B, T_TRIG_RATIOS, correct=False, score=0.1, occurred_at=NOW),
    ]
