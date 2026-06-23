"""Spaced-retrieval scheduler against the real forgetting curve (B7).

Spaced retrieval runs against the REAL forgetting curve, not a fixed "review in
3 days" rule. The model:

  - Retention decays exponentially: R(t) = exp(-t / S), where ``S`` is the
    memory STABILITY (the time constant of the curve) for one (learner, topic).
    R is the predicted probability the learner can still retrieve it now.
  - Stability GROWS with each successful, spaced retrieval (the spacing effect):
    a successful recall multiplies stability; the multiplier is larger the
    INDEPENDENT the recall was (an independent success consolidates more than a
    heavily-supported one) and larger when the recall happened after real decay
    (retrieving something you had nearly forgotten strengthens it more).
  - A failed retrieval RESETS stability toward its floor — the topic is fragile
    again and revision is due now.

Revision is "due" when predicted retention falls to the target retrievability
(default 0.85 — review just before you would forget, the efficient point on the
curve), or immediately after a failed recall.

This is deterministic and pure: the same evidence in yields the same schedule
out. It reads attempt evidence — including the keystone independent-vs-supported
flag — to estimate stability; it does NOT author mastery (that is CORE, owned by
the intelligence engine). Mastery's recency dimension and the retention gap are
the engine's read; this module turns the SAME forgetting model into a concrete
"revise this topic on <date>" plan.

Import-safe and offline: stdlib only. Accepts evidence as plain records so it
never requires pydantic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


# --- Forgetting-curve constants -------------------------------------------
# Initial stability (days) granted by a first successful retrieval. A first
# learn is fragile — it holds for about a day at the default target before the
# first reinforcement is due — and each spaced success extends it from there.
INITIAL_STABILITY_DAYS = 7.0
# Floor stability after a failed retrieval — the topic is fragile again.
MIN_STABILITY_DAYS = 0.5
# Cap so the schedule never proposes an absurdly distant review.
MAX_STABILITY_DAYS = 365.0
# Target retrievability at which revision becomes due. Review just before the
# curve drops below this — the efficient point (high R = wasted review; low R =
# relearning from scratch).
DEFAULT_TARGET_RETRIEVABILITY = 0.85
# How much an INDEPENDENT successful recall multiplies stability, versus a
# SUPPORTED one. Independent consolidation is stronger (the keystone flag).
_INDEPENDENT_GROWTH = 2.2
_SUPPORTED_GROWTH = 1.4
# Bonus to growth for retrieving after real decay (the spacing effect): a recall
# at low predicted retention strengthens more than an over-frequent one.
_SPACING_BONUS_MAX = 0.6


@dataclass(frozen=True)
class RetrievalObservation:
    """One retrieval attempt as the scheduler reads it. A trimmed view of an
    attempt event — only what the forgetting model needs."""

    occurred_at: datetime
    success: bool          # was the retrieval correct (>= pass)
    independent: bool      # the keystone flag: recalled unaided?
    # Optional partial credit in [0,1]; defaults from ``success`` when absent.
    score: float | None = None

    @property
    def effective_score(self) -> float:
        if self.score is not None:
            return self.score
        return 1.0 if self.success else 0.0


@dataclass(frozen=True)
class RevisionSchedule:
    """The computed retrieval plan for one (learner, topic)."""

    topic_id: str
    stability_days: float          # the curve's time constant after all evidence
    last_retrieval_at: datetime | None
    retention_now: float           # predicted P(recall) at ``asof``
    due_at: datetime | None        # when retention hits the target; None if no evidence
    is_due: bool                   # due at/before ``asof``
    plain_language: str            # learner-facing, never a number or the curve

    @property
    def overdue(self) -> bool:
        return self.is_due and self.due_at is not None


def predicted_retention(*, stability_days: float, days_since: float) -> float:
    """R(t) = exp(-t / S). Probability the learner can still retrieve it now."""
    if stability_days <= 0:
        return 0.0
    days_since = max(days_since, 0.0)
    return math.exp(-days_since / stability_days)


def _growth_multiplier(obs: RetrievalObservation, *, retention_at_recall: float) -> float:
    """How much a successful recall multiplies stability. Larger when independent
    and larger when recalled after real decay (the spacing effect)."""
    base = _INDEPENDENT_GROWTH if obs.independent else _SUPPORTED_GROWTH
    # Spacing bonus: low retention-at-recall (you nearly forgot) -> bigger gain.
    spacing = _SPACING_BONUS_MAX * (1.0 - retention_at_recall)
    # Partial credit scales the gain between a floor and the full multiplier.
    quality = obs.effective_score
    return 1.0 + (base - 1.0 + spacing) * quality


def estimate_stability(observations: Iterable[RetrievalObservation]) -> tuple[float, datetime | None]:
    """Replay the retrieval history into a current stability (days) and the time
    of the last retrieval. Deterministic.

    Each successful, spaced recall multiplies stability; a failure resets it
    toward the floor. Stability is clamped to [MIN, MAX].
    """
    ordered = sorted(observations, key=lambda o: o.occurred_at)
    stability = 0.0
    last_at: datetime | None = None
    for obs in ordered:
        if last_at is None:
            # First retrieval: a success seeds initial stability; a first failure
            # leaves the topic at the fragile floor.
            stability = INITIAL_STABILITY_DAYS if obs.success else MIN_STABILITY_DAYS
            last_at = obs.occurred_at
            continue
        days_since = (obs.occurred_at - last_at).total_seconds() / 86400.0
        ret_at_recall = predicted_retention(stability_days=stability, days_since=days_since)
        if obs.effective_score >= 0.5:
            stability *= _growth_multiplier(obs, retention_at_recall=ret_at_recall)
        else:
            # Failed recall: the topic is fragile again. Reset toward the floor.
            stability = MIN_STABILITY_DAYS
        stability = max(MIN_STABILITY_DAYS, min(stability, MAX_STABILITY_DAYS))
        last_at = obs.occurred_at
    return stability, last_at


def _due_at(*, stability_days: float, last_at: datetime, target: float) -> datetime:
    """Solve exp(-t/S) = target for t: t = -S * ln(target). The moment retention
    decays to the target retrievability — the efficient point to revise."""
    target = min(max(target, 1e-6), 0.999999)
    days = -stability_days * math.log(target)
    return last_at + timedelta(days=max(days, 0.0))


def _plain_language(*, has_evidence: bool, is_due: bool, retention_now: float) -> str:
    """Learner-facing wording. Never a number, never the curve (CONFIDENTIALITY
    SCRUB: plain language for learners)."""
    if not has_evidence:
        return "nothing to revise here yet"
    if is_due:
        return "revision is due"
    if retention_now >= 0.95:
        return "this is fresh, no revision needed yet"
    return "this is still solid, revision is coming up"


def schedule_topic(
    *,
    topic_id: str,
    observations: Iterable[RetrievalObservation],
    asof: datetime | None = None,
    target_retrievability: float = DEFAULT_TARGET_RETRIEVABILITY,
) -> RevisionSchedule:
    """Compute the spaced-retrieval schedule for one (learner, topic).

    Pure: identical observations + asof -> identical schedule. With no
    observations the topic is simply not yet on the revision plan.
    """
    asof = asof or datetime.now(timezone.utc)
    obs_list = list(observations)
    stability, last_at = estimate_stability(obs_list)

    if last_at is None:
        return RevisionSchedule(
            topic_id=topic_id,
            stability_days=0.0,
            last_retrieval_at=None,
            retention_now=0.0,
            due_at=None,
            is_due=False,
            plain_language=_plain_language(has_evidence=False, is_due=False, retention_now=0.0),
        )

    days_since = (asof - last_at).total_seconds() / 86400.0
    retention_now = predicted_retention(stability_days=stability, days_since=days_since)
    due_at = _due_at(stability_days=stability, last_at=last_at, target=target_retrievability)
    # A failed last recall (stability at floor and last obs failed) is due now.
    last_failed = obs_list and sorted(obs_list, key=lambda o: o.occurred_at)[-1].effective_score < 0.5
    is_due = bool(last_failed) or due_at <= asof

    return RevisionSchedule(
        topic_id=topic_id,
        stability_days=stability,
        last_retrieval_at=last_at,
        retention_now=retention_now,
        due_at=due_at,
        is_due=is_due,
        plain_language=_plain_language(has_evidence=True, is_due=is_due, retention_now=retention_now),
    )


def due_topics(
    schedules: Iterable[RevisionSchedule],
    *,
    asof: datetime | None = None,
) -> list[RevisionSchedule]:
    """Filter to the topics whose revision is due, soonest/most-overdue first.

    Drives a learner's "revise these now" queue. Most-decayed first: lower
    predicted retention surfaces ahead of higher.
    """
    asof = asof or datetime.now(timezone.utc)
    due = [s for s in schedules if s.is_due]
    due.sort(key=lambda s: (s.retention_now, s.due_at or asof))
    return due
