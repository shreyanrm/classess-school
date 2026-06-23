"""Quality + SAFETY filtering of learning signals (spine A4 — Track 2).

INVARIANT 7 — GENERATE-AND-VERIFY + SAFETY FILTERING before any example enters a
dataset. Only outputs that PASS the AI fabric's generate-and-verify gate become
positive training targets. Unsafe / toxic / low-confidence / contradictory
examples are dropped. Task classes are balanced so the small student is not
swamped by the high-frequency ocean.

This module respects (does not modify) the AI fabric's verify substrate: it
accepts a verifier callable shaped like ``ConfidenceGate.evaluate`` output (an
object with a ``served`` flag and a ``confidence``) or a simple predicate, and
treats anything below the gate as ineligible to be a positive target.

Curation is PURE and deterministic over its inputs.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Callable, Iterable

from .capture import LearningSignal

# A small, conservative toxicity / unsafe-content lexicon. A real deployment
# routes free text through the child-safety subsystem (A7) and the fabric's
# moderation; this is the deterministic floor that runs with no network.
_UNSAFE_TERMS = (
    "kill yourself",
    "self-harm",
    "suicide method",
    "make a bomb",
    "buy drugs",
    "hate speech",
)
_UNSAFE_RE = re.compile("|".join(re.escape(t) for t in _UNSAFE_TERMS), re.IGNORECASE)

# Default minimum reward for a signal to be eligible at all (low-confidence drop).
DEFAULT_MIN_REWARD = 0.5


@dataclass(frozen=True)
class CurationReport:
    """Transparent account of what curation did. Counts only, no PII."""

    kept: int
    dropped_unsafe: int
    dropped_low_confidence: int
    dropped_contradictory: int
    dropped_unverified_positive: int
    dropped_inadmissible: int
    balanced_capped: int
    per_class_kept: dict[str, int] = field(default_factory=dict)


# A verifier is anything that, given a signal, returns whether its output passes
# generate-and-verify and at what confidence. The default treats high-reward
# signals as verify-passing (used when no fabric verifier is injected/offline).
VerifierResult = tuple[bool, float]
Verifier = Callable[[LearningSignal], VerifierResult]


def _default_verifier(signal: LearningSignal) -> VerifierResult:
    """Offline floor: a signal already carrying a verify stamp is honoured;
    otherwise reward acts as a proxy confidence. Conservative — abstains low."""
    if signal.verify_passed is not None:
        return signal.verify_passed, float(signal.verify_confidence or 0.0)
    return signal.reward >= DEFAULT_MIN_REWARD, signal.reward


def is_unsafe(signal: LearningSignal) -> bool:
    """True if either side of the example contains apparent unsafe content."""
    return bool(_UNSAFE_RE.search(signal.input) or _UNSAFE_RE.search(signal.output))


class Curator:
    """Filters + balances admissible signals into clean training examples."""

    def __init__(
        self,
        *,
        min_reward: float = DEFAULT_MIN_REWARD,
        verifier: Verifier | None = None,
        max_per_class: int | None = None,
    ) -> None:
        self._min_reward = min_reward
        self._verifier = verifier or _default_verifier
        self._max_per_class = max_per_class

    def curate(self, signals: Iterable[LearningSignal]) -> tuple[list[LearningSignal], CurationReport]:
        """Return (clean_signals, report).

        Order of filters: admissibility -> safety -> contradiction -> low
        confidence -> generate-and-verify positive-target gate -> balance.
        """
        signals = list(signals)
        dropped_inadmissible = 0
        dropped_unsafe = 0
        dropped_low = 0
        dropped_contra = 0
        dropped_unverified = 0
        balanced_capped = 0

        # 1. Admissibility is non-negotiable (defence in depth; dataset also
        #    re-checks). An inadmissible signal never trains a model.
        stage: list[LearningSignal] = []
        for s in signals:
            if not s.admissible:
                dropped_inadmissible += 1
                continue
            stage.append(s)

        # 2. Safety: drop unsafe/toxic on either side.
        safe_stage: list[LearningSignal] = []
        for s in stage:
            if is_unsafe(s):
                dropped_unsafe += 1
                continue
            safe_stage.append(s)

        # 3. Contradiction: for the same (task_class, input) keep a single
        #    coherent target. If the SAME input maps to DIFFERENT outputs, the
        #    pair is contradictory and BOTH are dropped (a noisy label is worse
        #    than no label for a small student).
        by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
        for s in safe_stage:
            by_key[(s.task_class, s.input)].add(s.output)
        contradictory_keys = {k for k, outs in by_key.items() if len(outs) > 1}
        nocontra: list[LearningSignal] = []
        for s in safe_stage:
            if (s.task_class, s.input) in contradictory_keys:
                dropped_contra += 1
                continue
            nocontra.append(s)

        # 4. Low confidence + 5. generate-and-verify positive-target gate.
        verified: list[LearningSignal] = []
        for s in nocontra:
            if s.reward < self._min_reward:
                dropped_low += 1
                continue
            passed, conf = self._verifier(s)
            if not passed:
                dropped_unverified += 1
                continue
            verified.append(
                replace(s, verify_passed=True, verify_confidence=conf)
            )

        # 6. Balance task classes — cap each class so none dominates the student.
        per_class: dict[str, int] = defaultdict(int)
        balanced: list[LearningSignal] = []
        # Deterministic ordering: by signal_id within stable input order.
        for s in sorted(verified, key=lambda x: (x.task_class, x.signal_id)):
            if self._max_per_class is not None and per_class[s.task_class] >= self._max_per_class:
                balanced_capped += 1
                continue
            per_class[s.task_class] += 1
            balanced.append(s)

        report = CurationReport(
            kept=len(balanced),
            dropped_unsafe=dropped_unsafe,
            dropped_low_confidence=dropped_low,
            dropped_contradictory=dropped_contra,
            dropped_unverified_positive=dropped_unverified,
            dropped_inadmissible=dropped_inadmissible,
            balanced_capped=balanced_capped,
            per_class_kept=dict(per_class),
        )
        return balanced, report
