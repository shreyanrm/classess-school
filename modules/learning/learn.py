"""The pose -> struggle -> reveal flow controller (B7).

Learning is POSE -> STRUGGLE -> REVEAL, never explain-first. The controller
enforces that order as a small, explicit state machine:

  POSED      -> a problem is posed; nothing is explained yet.
  STRUGGLING -> the learner is given room to attempt. Help is GATED: a reveal or
                a scaffold is refused until there has been a GENUINE attempt
                (real time-on-task and/or a submitted try). This is the
                anti-explain-first guard — you cannot skip straight to the answer.
  REVEALED   -> only after a genuine attempt: the system reveals / scaffolds.
                Whether help was used is RECORDED and flows into the attempt's
                independent-vs-supported flag.
  RESOLVED   -> the attempt is finalized into an evidence event. The
                independent-vs-supported flag is set from whether any help was
                used: a reveal/scaffold consumed -> SUPPORTED; a clean unaided
                solve -> the Independent rung -> INDEPENDENT.

The controller produces the attempt EVIDENCE; it does not author mastery (CORE,
owned by the intelligence engine). It records HOW the answer was produced, which
is the single most important bit in the evidence layer.

A genuine-attempt gate (minimum engaged time / an explicit submitted try) stops
the reveal being used as an explain-first shortcut. The threshold is tunable per
item; it is never zero.

Pure and import-safe: no I/O. Emitting the finalized attempt is delegated to
:mod:`learning.events` (which degrades to an in-memory append-only sink).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .ladder import (
    AssistanceRung,
    attempt_mode_of,
    coherent_attempt_fields,
    is_unaided_demonstration,
)

Phase = Literal["posed", "struggling", "revealed", "resolved"]

# A genuine attempt requires at least this much engaged time before any reveal
# or scaffold is allowed — the anti-explain-first guard. Never zero. Tunable
# per item via :meth:`LearnSession.pose`.
DEFAULT_MIN_STRUGGLE_MS = 15_000


class StruggleNotGenuineError(RuntimeError):
    """Raised when a reveal/scaffold is requested before a genuine attempt.

    This is the load-bearing guard that keeps learning pose-first: help is
    refused until the learner has genuinely engaged.
    """


@dataclass
class LearnSession:
    """One pose -> struggle -> reveal cycle for a single posed problem.

    Tracks engaged time, whether the learner submitted a try, and whether any
    help (reveal/scaffold) was used — the inputs to the independent-vs-supported
    flag the finalized attempt carries.
    """

    topic_id: str
    question_id: str | None = None
    difficulty: float = 0.5
    # The rung the system is WILLING to use if the learner asks for help. Set at
    # pose time from the faded ladder; until help is actually used the attempt
    # stays a candidate for an Independent (unaided) demonstration.
    offered_rung: AssistanceRung = "Hint"
    min_struggle_ms: int = DEFAULT_MIN_STRUGGLE_MS

    phase: Phase = "posed"
    engaged_ms: int = 0
    submitted_try: bool = False
    help_used: bool = False
    rung_used: str | None = None   # the actual rung consumed, if any help used
    outcome_at: datetime | None = None

    # ----- POSE -----------------------------------------------------------
    @classmethod
    def pose(
        cls,
        *,
        topic_id: str,
        offered_rung: str = "Hint",
        question_id: str | None = None,
        difficulty: float = 0.5,
        min_struggle_ms: int = DEFAULT_MIN_STRUGGLE_MS,
    ) -> "LearnSession":
        """Pose a problem. Nothing is explained — the learner is handed the
        problem and the floor. ``offered_rung`` is the help the system will give
        IF asked, after a genuine attempt."""
        if min_struggle_ms <= 0:
            # The guard is never zero — that would permit explain-first.
            min_struggle_ms = DEFAULT_MIN_STRUGGLE_MS
        return cls(
            topic_id=topic_id,
            question_id=question_id,
            difficulty=difficulty,
            offered_rung=offered_rung,  # type: ignore[arg-type]
            min_struggle_ms=min_struggle_ms,
            phase="posed",
        )

    # ----- STRUGGLE -------------------------------------------------------
    def record_engagement(self, *, elapsed_ms: int, submitted_try: bool = False) -> None:
        """Record time-on-task and whether the learner has submitted a try. The
        learner enters/stays in the STRUGGLING phase."""
        if self.phase in ("revealed", "resolved"):
            raise RuntimeError("cannot record engagement after the reveal/resolve.")
        self.engaged_ms += max(0, int(elapsed_ms))
        self.submitted_try = self.submitted_try or submitted_try
        self.phase = "struggling"

    @property
    def attempt_is_genuine(self) -> bool:
        """A genuine attempt = enough engaged time, OR an explicit submitted try.
        The gate that a reveal cannot bypass."""
        return self.submitted_try or self.engaged_ms >= self.min_struggle_ms

    # ----- REVEAL / SCAFFOLD ---------------------------------------------
    def can_reveal(self) -> bool:
        return self.phase in ("struggling", "posed") and self.attempt_is_genuine

    def reveal(self, *, rung: str | None = None) -> str:
        """Reveal / scaffold — ONLY after a genuine attempt. Records that help
        was used at ``rung`` (defaults to the offered rung), which makes the
        eventual attempt SUPPORTED.

        Raises :class:`StruggleNotGenuineError` if invoked before a genuine
        attempt — the anti-explain-first guard.
        """
        if not self.attempt_is_genuine:
            raise StruggleNotGenuineError(
                "Reveal refused: there has not been a genuine attempt yet. "
                "Learning is pose -> struggle -> reveal; help comes after the try."
            )
        used = rung or self.offered_rung
        if is_unaided_demonstration(used):
            # 'Independent' is not a help rung; revealing at it is incoherent.
            used = "Hint"
        self.help_used = True
        self.rung_used = used
        self.phase = "revealed"
        return used

    # ----- RESOLVE -> evidence -------------------------------------------
    def resolve(
        self,
        *,
        correct: bool,
        score: float | None = None,
        time_taken_ms: int | None = None,
        attempt_number: int = 1,
        asof: datetime | None = None,
    ) -> dict[str, Any]:
        """Finalize the cycle into an attempt-evidence PAYLOAD.

        The independent-vs-supported flag is set from whether help was used:
          - help used  -> SUPPORTED at the rung consumed.
          - no help    -> the Independent rung -> INDEPENDENT (an unaided
            demonstration, the only evidence that can confirm independent
            mastery).

        Returns the validated attempt payload; the caller emits it via
        :mod:`learning.events`.
        """
        from . import events as _events  # lazy: keep learn import-safe

        self.outcome_at = asof or datetime.now(timezone.utc)
        if self.help_used and self.rung_used is not None:
            rung = self.rung_used
        else:
            rung = "Independent"
        mode, level = coherent_attempt_fields(rung)
        self.phase = "resolved"
        return _events.build_attempt_payload(
            topic_id=self.topic_id,
            assistance_level=level,
            correct=correct,
            difficulty=self.difficulty,
            time_taken_ms=time_taken_ms if time_taken_ms is not None else self.engaged_ms,
            score=score,
            question_id=self.question_id,
            attempt_number=attempt_number,
            mode=mode,
        )

    # ----- explainability -------------------------------------------------
    @property
    def used_help(self) -> bool:
        """The independent-vs-supported flag, plainly: did the learner use help?"""
        return self.help_used

    def summary(self) -> dict[str, Any]:
        """A plain, PII-free trace of the cycle for surfaces/audit. No names, no
        raw mastery number — clean prose only."""
        return {
            "topic_id": self.topic_id,
            "phase": self.phase,
            "genuine_attempt": self.attempt_is_genuine,
            "help_used": self.help_used,
            "rung_used": self.rung_used,
            "independent": not self.help_used,
            "engaged_ms": self.engaged_ms,
        }
