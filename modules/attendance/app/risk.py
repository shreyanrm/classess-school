"""Attendance risk detection (B8 / d8 "Risk, reconciliation & response").

Turns attendance from a record into an early-warning SIGNAL. Detects:

  - CONSECUTIVE absence — N school days absent in a row.
  - CHRONIC-absence risk — absence rate over a window crosses a threshold
    (the chronic-absenteeism definition is configurable per board/institution).
  - PATTERN risk — same-weekday / period-of-day patterns: a learner who is
    repeatedly absent on a particular weekday (e.g. every Monday) or from the
    post-lunch periods, even when overall attendance looks fine.

DESIGN (INVARIANT 7, generate-and-verify + confidence gate; principle 7,
evidence over assertion):
  - Every finding carries the EVIDENCE (the dated marks it was computed from),
    a confidence in [0,1], and a plain-language rationale (explainability).
  - A finding is a SIGNAL, never a verdict and never misconduct (d8: conflicts
    are flagged for human review, "rather than treating them as misconduct").
    Detection RECOMMENDS; the response (parent communication, catch-up plan) is
    a human-owned, consent-gated action emitted via events, never auto-fired —
    so every finding carries ``needs_human_review``.

PII: works entirely on opaque learner refs (``canonical_uuid``) and dated
statuses. No name, no PII.

Import-safe: pure functions over plain data; no I/O, no provider, no secret read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable, List, Mapping, Optional, Sequence

from .capture import Status


class RiskKind(str, Enum):
    CONSECUTIVE = "consecutive"
    CHRONIC = "chronic"
    PATTERN = "pattern"


class RiskSeverity(str, Enum):
    """Coarse, plain-language bands — never a raw score shown to a human."""

    WATCH = "watch"        # early — keep an eye
    CONCERN = "concern"    # crossed a threshold — prepare a response
    URGENT = "urgent"      # well past threshold — needs action now


# Statuses that count as a "miss" for risk purposes. EXCUSED is NOT a miss — an
# approved absence is not a risk signal (d8: not misconduct).
_MISS = frozenset({Status.ABSENT})
_ATTENDED = frozenset({Status.PRESENT, Status.LATE})


@dataclass(frozen=True)
class RiskConfig:
    """Thresholds. Configurable per board/institution (board-agnostic, principle
    6) — never hard-coded into the logic. Defaults are conservative starting
    points, not policy."""

    consecutive_watch: int = 2
    consecutive_concern: int = 3
    consecutive_urgent: int = 5

    chronic_window_days: int = 30
    chronic_min_marks: int = 8           # need enough evidence before flagging
    chronic_concern_rate: float = 0.10   # 10% absence over the window
    chronic_urgent_rate: float = 0.20

    pattern_min_occurrences: int = 3     # min misses in a slice before a pattern
    pattern_concern_rate: float = 0.40   # missed 40%+ of that weekday/slot


@dataclass(frozen=True)
class RiskFinding:
    """A detected risk. A signal with full lineage, never a judgment.

    ``needs_human_review`` is always ``True``: detection recommends, a human
    decides and owns any response.
    """

    canonical_uuid: str
    risk_kind: str
    severity: str
    confidence: float
    rationale: str                       # plain-language why (explainability)
    evidence_days: List[str] = field(default_factory=list)  # ISO dates it rests on
    metric: Optional[float] = None       # the measured quantity (rate, run)
    detail: Mapping[str, str] = field(default_factory=dict)
    needs_human_review: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1].")


# ---------------------------------------------------------------------------
# Internal: a normalised, sorted day record.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Day:
    date: str
    status: Status
    period_of_day: Optional[str] = None


def _coerce_status(value: Any) -> Status:
    if isinstance(value, Status):
        return value
    return Status(str(value))


def _parse_day(day: str) -> date:
    return datetime.fromisoformat(day).date() if "T" in day else date.fromisoformat(day)


def _normalise_history(history: Mapping[str, Any]) -> "tuple[str, List[_Day]]":
    """Accept the documented history shape:
    ``{"canonical_uuid": ..., "days": [{"date", "status", "period_of_day"?}, ...]}``.
    """
    cuid = history.get("canonical_uuid", "")
    days_in = history.get("days", []) or []
    days: List[_Day] = []
    for d in days_in:
        days.append(
            _Day(
                date=d["date"],
                status=_coerce_status(d.get("status", "unknown")),
                period_of_day=d.get("period_of_day"),
            )
        )
    days.sort(key=lambda x: _parse_day(x.date))
    return cuid, days


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def _detect_consecutive(
    cuid: str, days: Sequence[_Day], cfg: RiskConfig
) -> Optional[RiskFinding]:
    """Trailing run of consecutive absences ending at the latest mark."""
    if not days:
        return None
    run: List[str] = []
    for d in reversed(days):
        if d.status in _MISS:
            run.append(d.date)
        else:
            break
    n = len(run)
    if n < cfg.consecutive_watch:
        return None
    if n >= cfg.consecutive_urgent:
        sev = RiskSeverity.URGENT
    elif n >= cfg.consecutive_concern:
        sev = RiskSeverity.CONCERN
    else:
        sev = RiskSeverity.WATCH
    confidence = min(0.99, 0.5 + 0.1 * n)
    return RiskFinding(
        canonical_uuid=cuid,
        risk_kind=RiskKind.CONSECUTIVE.value,
        severity=sev.value,
        confidence=confidence,
        rationale=(
            f"Absent {n} school day(s) in a row through {run[0]}. Consecutive "
            "absence is the earliest signal that a learner is disengaging."
        ),
        evidence_days=list(reversed(run)),
        metric=float(n),
    )


def _detect_chronic(
    cuid: str, days: Sequence[_Day], cfg: RiskConfig
) -> Optional[RiskFinding]:
    """Chronic-absence risk over the configured window."""
    if not days:
        return None
    latest = _parse_day(days[-1].date)
    window = [
        d for d in days
        if (latest - _parse_day(d.date)).days < cfg.chronic_window_days
    ]
    counted = [d for d in window if d.status in _MISS or d.status in _ATTENDED]
    if len(counted) < cfg.chronic_min_marks:
        return None
    misses = [d for d in counted if d.status in _MISS]
    rate = len(misses) / len(counted)
    if rate < cfg.chronic_concern_rate:
        return None
    sev = (
        RiskSeverity.URGENT if rate >= cfg.chronic_urgent_rate else RiskSeverity.CONCERN
    )
    confidence = min(
        0.99, 0.6 + min(0.3, (rate - cfg.chronic_concern_rate)) + 0.01 * len(counted)
    )
    return RiskFinding(
        canonical_uuid=cuid,
        risk_kind=RiskKind.CHRONIC.value,
        severity=sev.value,
        confidence=confidence,
        rationale=(
            f"Absent on {len(misses)} of {len(counted)} counted days "
            f"({rate:.0%}) over the last {cfg.chronic_window_days} days — at or "
            "above the chronic-absence threshold for this institution."
        ),
        evidence_days=[d.date for d in misses],
        metric=round(rate, 4),
    )


_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _detect_patterns(
    cuid: str, days: Sequence[_Day], cfg: RiskConfig
) -> List[RiskFinding]:
    """Same-weekday and period-of-day patterns.

    Catches the learner who attends overall but repeatedly skips a particular
    weekday (e.g. every Monday) or the post-lunch periods (d8).
    """
    findings: List[RiskFinding] = []

    def _slice(label_kind: str, value: str, slice_days: Sequence[_Day]) -> None:
        counted = [d for d in slice_days if d.status in _MISS or d.status in _ATTENDED]
        misses = [d for d in counted if d.status in _MISS]
        if len(misses) < cfg.pattern_min_occurrences or not counted:
            return
        rate = len(misses) / len(counted)
        if rate < cfg.pattern_concern_rate:
            return
        sev = RiskSeverity.CONCERN
        confidence = min(0.95, 0.5 + (rate - cfg.pattern_concern_rate) + 0.02 * len(misses))
        readable = "weekday" if label_kind == "weekday" else "time slot"
        findings.append(
            RiskFinding(
                canonical_uuid=cuid,
                risk_kind=RiskKind.PATTERN.value,
                severity=sev.value,
                confidence=confidence,
                rationale=(
                    f"Missed {len(misses)} of {len(counted)} sessions ({rate:.0%}) "
                    f"for one {readable} ({value}) — a targeted pattern, not random "
                    "absence. Worth a human look, not an accusation."
                ),
                evidence_days=[d.date for d in misses],
                metric=round(rate, 4),
                detail={label_kind: value},
            )
        )

    # By weekday.
    by_weekday: dict[int, List[_Day]] = {}
    for d in days:
        wd = _parse_day(d.date).weekday()
        by_weekday.setdefault(wd, []).append(d)
    for wd, slice_days in by_weekday.items():
        _slice("weekday", _WEEKDAYS[wd], slice_days)

    # By period of day (e.g. post-lunch), when present in the record.
    by_slot: dict[str, List[_Day]] = {}
    for d in days:
        if d.period_of_day is not None:
            by_slot.setdefault(d.period_of_day, []).append(d)
    for slot, slice_days in by_slot.items():
        _slice("period_of_day", slot, slice_days)

    return findings


def detect_risks(
    history: Mapping[str, Any], config: Optional[RiskConfig] = None
) -> List[RiskFinding]:
    """Run every detector over one learner's attendance history.

    ``history`` is ``{"canonical_uuid": <opaque ref>, "days": [{"date",
    "status", "period_of_day"?}, ...]}``. Returns all findings; each is
    independent, carries its own evidence + confidence + plain-language
    rationale, and is a recommendation only (``needs_human_review`` is always
    ``True``). Responses are owned by humans and fired via events.py.
    """
    cfg = config or RiskConfig()
    cuid, days = _normalise_history(history)
    if not days:
        return []

    findings: List[RiskFinding] = []
    consecutive = _detect_consecutive(cuid, days, cfg)
    if consecutive is not None:
        findings.append(consecutive)
    chronic = _detect_chronic(cuid, days, cfg)
    if chronic is not None:
        findings.append(chronic)
    findings.extend(_detect_patterns(cuid, days, cfg))
    return findings
