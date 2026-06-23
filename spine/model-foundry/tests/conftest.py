"""Synthetic, PII-free, offline fixtures for the model-foundry tests.

Builds event envelopes and consent records in memory. UUIDs are deterministic so
datasets and content hashes are reproducible. No network, no provider, no
training.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

# Import the package without installation.
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from app.consent_gate import (  # noqa: E402
    MODEL_IMPROVEMENT_SCOPE,
    ConsentGate,
    ConsentRecord,
    ConsentStatus,
)

# Deterministic opaque ids — random-shaped tokens, never derived from PII.
ADULT = UUID("aaaaaaaa-0000-4000-8000-000000000001")
TEEN = UUID("bbbbbbbb-0000-4000-8000-000000000002")
CHILD = UUID("cccccccc-0000-4000-8000-000000000003")
GUARDIAN = UUID("dddddddd-0000-4000-8000-000000000004")
APPROVER = UUID("eeeeeeee-0000-4000-8000-000000000005")

CONSENT_ADULT = UUID("c0000000-0000-4000-8000-000000000001")
CONSENT_TEEN = UUID("c0000000-0000-4000-8000-000000000002")
CONSENT_CHILD = UUID("c0000000-0000-4000-8000-000000000003")
CONSENT_NARROW = UUID("c0000000-0000-4000-8000-000000000004")  # wrong scope

TOPIC = UUID("70910000-0000-4000-8000-000000000301")
NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)

_counter = {"n": 0}


def _next_event_id() -> UUID:
    _counter["n"] += 1
    return UUID(f"e0e00000-0000-4000-8000-{_counter['n']:012d}")


def reset_ids() -> None:
    _counter["n"] = 0


def attempt_event(
    *,
    subject: UUID = ADULT,
    consent_ref: UUID = CONSENT_ADULT,
    correct: bool = True,
    difficulty: float = 0.5,
    mode: str = "independent",
    assistance_level: str = "Independent",
    event_id: UUID | None = None,
) -> dict:
    return {
        "event_id": event_id or _next_event_id(),
        "schema_version": "v1",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "app": "school",
        "canonical_uuid": subject,
        "purpose": "mastery",
        "consent_ref": consent_ref,
        "type": "attempt.recorded",
        "payload": {
            "attempt_id": str(_next_event_id()),
            "ontology": {"topic_id": str(TOPIC)},
            "mode": mode,
            "assistance_level": assistance_level,
            "correct": correct,
            "score": 1.0 if correct else 0.0,
            "time_taken_ms": 30000,
            "difficulty": difficulty,
            "attempt_number": 1,
        },
    }


def mastery_event(
    *,
    subject: UUID = ADULT,
    consent_ref: UUID = CONSENT_ADULT,
    band: str = "secure",
    composite: float = 0.8,
    gap_type: str | None = "procedural",
    gap_confirmed: bool = True,
    rationale: str = "method steps unreliable on multi-step items",
    event_id: UUID | None = None,
) -> dict:
    gaps = []
    if gap_type is not None:
        gaps.append(
            {
                "gap_type": gap_type,
                "confidence": 0.9,
                "confirmed": gap_confirmed,
                "evidence_event_ids": [str(_next_event_id())],
                "rationale": rationale,
            }
        )
    return {
        "event_id": event_id or _next_event_id(),
        "schema_version": "v1",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "app": "school",
        "canonical_uuid": subject,
        "purpose": "mastery",
        "consent_ref": consent_ref,
        "type": "mastery.updated",
        "payload": {
            "subject": str(subject),
            "ontology": {"topic_id": str(TOPIC)},
            "reading": {
                "dimensions": {
                    "performance": 0.8,
                    "reliability": 0.8,
                    "independence": 0.8,
                    "difficulty": 0.5,
                    "recency": 0.9,
                    "consistency": 0.8,
                },
                "composite": composite,
                "band": band,
                "independent": True,
            },
            "gaps": gaps,
            "source_event_ids": [str(_next_event_id())],
        },
    }


def consent_granted_event(
    *,
    subject: UUID,
    consent_ref: UUID,
    age_tier: str,
    scope: str = MODEL_IMPROVEMENT_SCOPE,
    granted_by: UUID | None = None,
) -> dict:
    return {
        "event_id": _next_event_id(),
        "schema_version": "v1",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "app": "school",
        "canonical_uuid": subject,
        "purpose": "account",
        "consent_ref": consent_ref,
        "type": "consent.granted",
        "payload": {
            "consent_id": str(consent_ref),
            "scope": scope,
            "purpose": "mastery",
            "age_tier": age_tier,
            "granted_by": str(granted_by or subject),
        },
    }


def consent_revoked_event(*, subject: UUID, consent_ref: UUID) -> dict:
    return {
        "event_id": _next_event_id(),
        "schema_version": "v1",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "app": "school",
        "canonical_uuid": subject,
        "purpose": "account",
        "consent_ref": consent_ref,
        "type": "consent.revoked",
        "payload": {"consent_id": str(consent_ref), "revoked_by": str(subject)},
    }


def gate_with_all_tiers() -> ConsentGate:
    """A gate where the adult + (guardian-granted) teen are admissible, the child
    is blocked, and the narrow-scope consent does not permit model improvement."""
    return ConsentGate(
        [
            ConsentRecord(CONSENT_ADULT, ADULT, "adult", MODEL_IMPROVEMENT_SCOPE),
            ConsentRecord(CONSENT_TEEN, TEEN, "teen", MODEL_IMPROVEMENT_SCOPE, granted_by=GUARDIAN),
            ConsentRecord(CONSENT_CHILD, CHILD, "child", MODEL_IMPROVEMENT_SCOPE, granted_by=GUARDIAN),
            ConsentRecord(CONSENT_NARROW, ADULT, "adult", "learning_behavior"),
        ]
    )


@pytest.fixture(autouse=True)
def _reset_ids():
    reset_ids()
    yield
    reset_ids()


@pytest.fixture
def gate() -> ConsentGate:
    return gate_with_all_tiers()
