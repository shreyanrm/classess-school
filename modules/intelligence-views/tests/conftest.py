"""Test fixtures for intelligence-views (B11).

Import-safe and offline: builds spine ``LearnerProfile`` projections from
synthetic, PII-free events in memory — no network, no provider, no build step.
Profiles drive every view (dashboards, quadrant, target analytics, prediction,
ask-anything), so the composition is exercised end to end deterministically.

The module package, the spine intelligence package, and the spine workflow
package are put on ``sys.path`` as source (no install is run, per the build law).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

_MODULE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _MODULE_ROOT.parents[1]  # .../classess-school
_SPINE_INTELLIGENCE = _REPO_ROOT / "spine" / "intelligence"
_SPINE_WORKFLOW = _REPO_ROOT / "spine" / "workflow"

# Module package first so ``import app`` inside the module resolves to B11.
for p in (_MODULE_ROOT, _SPINE_INTELLIGENCE, _SPINE_WORKFLOW):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Spine intelligence models/profile — imported by absolute file location so the
# module's own ``app`` package does not shadow it.
import importlib.util


def _load_spine_intelligence():
    """Load the spine intelligence ``app`` package as ``spine_intelligence`` so it
    coexists with the module's ``app`` package on the path."""
    pkg_dir = _SPINE_INTELLIGENCE / "app"
    if "spine_intelligence" in sys.modules:
        return sys.modules["spine_intelligence"]
    import types

    pkg = types.ModuleType("spine_intelligence")
    pkg.__path__ = [str(pkg_dir)]
    sys.modules["spine_intelligence"] = pkg
    for name in ("models", "evidence", "mastery", "gaps", "profile"):
        spec = importlib.util.spec_from_file_location(
            f"spine_intelligence.{name}", pkg_dir / f"{name}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"spine_intelligence.{name}"] = mod
        spec.loader.exec_module(mod)
    return pkg


_si = _load_spine_intelligence()
from spine_intelligence.models import EventEnvelope  # type: ignore  # noqa: E402
from spine_intelligence.profile import build_profile  # type: ignore  # noqa: E402

# Deterministic opaque ids (no PII — random-shaped tokens).
LEARNER_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
LEARNER_B = UUID("bbbbbbbb-0000-4000-8000-000000000002")
LEARNER_C = UUID("cccccccc-0000-4000-8000-000000000003")
CONSENT = UUID("dddddddd-0000-4000-8000-000000000004")
OWNER = UUID("eeeeeeee-0000-4000-8000-000000000005")

T_TRIG_RATIOS = UUID("70910000-0000-4000-8000-000000000306")
T_FRACTIONS = UUID("70910000-0000-4000-8000-000000000401")

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
    occurred_at: datetime | None = None,
) -> EventEnvelope:
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
            "attempt_number": 1,
        },
    )


def indep(subject, topic_id, *, correct=True, **kw):
    return attempt_event(
        subject=subject, topic_id=topic_id, mode="independent",
        assistance_level="Independent", correct=correct, **kw,
    )


def supported(subject, topic_id, *, correct=True, assistance_level="Coach", **kw):
    return attempt_event(
        subject=subject, topic_id=topic_id, mode="supported",
        assistance_level=assistance_level, correct=correct, **kw,
    )


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


def has_no_emoji(text: str) -> bool:
    """True when ``text`` contains no emoji. Plain typographic punctuation such as
    an em-dash is allowed (it is not an emoji); the confidentiality rule forbids
    emoji and exclamation marks in product copy, not Unicode punctuation."""
    for ch in text:
        code = ord(ch)
        if (
            0x1F000 <= code <= 0x1FAFF  # symbols, pictographs, emoji
            or 0x2600 <= code <= 0x27BF  # misc symbols + dingbats
            or 0x1F1E6 <= code <= 0x1F1FF  # regional indicators
            or code in (0x2122, 0x2139)  # trade mark, info
            or 0xFE00 <= code <= 0xFE0F  # variation selectors
        ):
            return False
    return True


def make_profile(subject: UUID, events: list[EventEnvelope]):
    """Build a spine LearnerProfile from this learner's events."""
    mine = [e for e in events if e.canonical_uuid == subject]
    return build_profile(mine, subject=subject, asof=NOW)


@pytest.fixture
def strong_cohort():
    """Two learners with strong, independent, fresh mastery on the trig topic.

    Returns (profiles, topic_id)."""
    events: list[EventEnvelope] = []
    for learner in (LEARNER_A, LEARNER_B):
        for _ in range(4):
            events.append(indep(learner, T_TRIG_RATIOS, correct=True, score=1.0, difficulty=0.6))
    profiles = [make_profile(LEARNER_A, events), make_profile(LEARNER_B, events)]
    return profiles, T_TRIG_RATIOS


@pytest.fixture
def gap_cohort():
    """Two learners with a CONFIRMED support-dependency gap on the trig topic:
    repeated supported success, no independent success — exactly the gap the
    Independence dimension exists to surface.

    Returns (profiles, topic_id)."""
    events: list[EventEnvelope] = []
    for learner in (LEARNER_A, LEARNER_B):
        for _ in range(3):
            events.append(
                supported(learner, T_TRIG_RATIOS, correct=True, score=0.9,
                          assistance_level="Coach", difficulty=0.5)
            )
        # an independent failure corroborates the dependency
        events.append(indep(learner, T_TRIG_RATIOS, correct=False, score=0.2, difficulty=0.5))
    profiles = [make_profile(LEARNER_A, events), make_profile(LEARNER_B, events)]
    return profiles, T_TRIG_RATIOS


@pytest.fixture
def single_score_cohort():
    """One learner, ONE bad independent attempt on the topic. Must NOT produce a
    confirmed gap (never-from-one-score) and so must NOT raise a dashboard alert.

    Returns (profiles, topic_id)."""
    events = [indep(LEARNER_C, T_TRIG_RATIOS, correct=False, score=0.2, difficulty=0.5)]
    profiles = [make_profile(LEARNER_C, events)]
    return profiles, T_TRIG_RATIOS
