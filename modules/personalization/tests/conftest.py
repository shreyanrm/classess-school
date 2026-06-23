"""Shared, deterministic, PII-free fixtures for the personalization suite.

Everything here is opaque ids and behavioural signals only — no questionnaire,
no PII, no network, no DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.consent_gate import PersonalizationConsent, TraitKind
from app.infer import OnboardingChoice, Signal, SignalKind


def _id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def asof() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def learner() -> str:
    """An opaque canonical_uuid — never derived from PII."""
    return _id()


@pytest.fixture
def topic_math() -> str:
    return _id()


@pytest.fixture
def topic_science() -> str:
    return _id()


@pytest.fixture
def adult_consent(learner: str) -> PersonalizationConsent:
    """An adult-tier consent covering the full set of inferable traits."""
    return PersonalizationConsent(
        consent_id=_id(),
        subject=learner,
        age_tier="adult",
        scopes=frozenset({"profiling", "preferences-hints"}),
        traits=None,  # full tier ceiling
        granted_by=learner,
    )


@pytest.fixture
def child_consent(learner: str) -> PersonalizationConsent:
    """A child-tier consent: shallowest profiling, guardian-granted."""
    return PersonalizationConsent(
        consent_id=_id(),
        subject=learner,
        age_tier="child",
        scopes=frozenset({"profiling", "preferences-hints"}),
        traits=None,  # the child ceiling (interest + preferred_subject only)
        granted_by=_id(),  # a guardian, opaque
    )


@pytest.fixture
def rich_signals(topic_math: str, topic_science: str) -> list[Signal]:
    """A behavioural history that should light up every adult-tier trait.

    Strong, repeated, independent-correct activity on maths; lighter on science;
    a clear video-format affinity; deliberate session rhythm. NO questionnaire.
    """
    signals: list[Signal] = []
    # Heavy engagement + independent-correct attempts on maths (interest,
    # preferred subject, strength).
    for _ in range(5):
        signals.append(
            Signal(signal_id=_id(), kind=SignalKind.TOPIC_ENGAGEMENT, subject_id=topic_math, weight=2.0, dwell_ms=40_000)
        )
    for _ in range(4):
        signals.append(
            Signal(
                signal_id=_id(),
                kind=SignalKind.ATTEMPT,
                subject_id=topic_math,
                correct=True,
                independent=True,
                weight=2.0,
                dwell_ms=45_000,
            )
        )
    # Lighter science engagement.
    for _ in range(2):
        signals.append(
            Signal(signal_id=_id(), kind=SignalKind.TOPIC_ENGAGEMENT, subject_id=topic_science, weight=1.0, dwell_ms=30_000)
        )
    # Strong video format affinity (learning style — adult only).
    for _ in range(4):
        signals.append(
            Signal(signal_id=_id(), kind=SignalKind.CONTENT_INTERACTION, subject_id=topic_math, content_format="video", weight=2.0)
        )
    return signals


@pytest.fixture
def goal_choice() -> OnboardingChoice:
    """A single light onboarding tap — NOT a questionnaire answer."""
    return OnboardingChoice(choice_id=_id(), kind="goal", value="exam-readiness")
