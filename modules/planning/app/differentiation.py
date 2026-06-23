"""Differentiation & readiness-aware planning (d6).

Plans account for student readiness and prior evidence. The planner draws on the
mastery model (CONSUMED from the spine intelligence engine — never authored here)
to assign each learner a task pitched at their band.

The keystone discipline: differentiation RESPECTS THE MASTERY BANDS. A learner is
only ever assigned a task whose declared bands include the learner's own band; a
learner with no matching task is left UNASSIGNED rather than mis-assigned across a
band. The band drives the task — never a name, never PII (INVARIANT 1 + 2): a
learner is an opaque ``canonical_uuid``.

Human authority: differentiation PREPARES assignments. The mapping of opaque
learner ids to tasks is a recommendation a teacher reviews; nothing consequential
auto-fires.

Pure, deterministic, dependency-free: same readings + same task bank -> same
assignments out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .events import EventLog, EventType


class MasteryBand(str, Enum):
    """The plain-language mastery bands consumed from the spine engine. The order
    is the readiness ladder differentiation pitches tasks along."""

    EMERGING = "emerging"
    DEVELOPING = "developing"
    SECURE = "secure"
    EXTENDING = "extending"


def band_for_mastery(mastery: float) -> MasteryBand:
    """Map a mastery reading in [0,1] to a band.

    Boundaries (inclusive lower bound): < 0.4 emerging, < 0.7 developing,
    < 0.9 secure, >= 0.9 extending."""
    if not 0.0 <= mastery <= 1.0:
        raise ValueError("mastery must be in [0,1].")
    if mastery < 0.4:
        return MasteryBand.EMERGING
    if mastery < 0.7:
        return MasteryBand.DEVELOPING
    if mastery < 0.9:
        return MasteryBand.SECURE
    return MasteryBand.EXTENDING


@dataclass(frozen=True)
class LearnerReadiness:
    """One learner's readiness reading for one outcome, consumed from the spine.

    PII-free: ``canonical_uuid`` is the opaque identity token; ``mastery`` is the
    mastery reading in [0,1]; the band is derived, never a fixed label."""

    canonical_uuid: str
    outcome_id: str
    mastery: float

    def __post_init__(self) -> None:
        if not self.canonical_uuid:
            raise ValueError("LearnerReadiness.canonical_uuid is required (opaque token).")
        if not self.outcome_id:
            raise ValueError("LearnerReadiness.outcome_id is required (opaque token).")
        if not 0.0 <= self.mastery <= 1.0:
            raise ValueError("mastery must be in [0,1].")

    @property
    def band(self) -> MasteryBand:
        return band_for_mastery(self.mastery)


@dataclass(frozen=True)
class DifferentiatedTask:
    """A task from the bank, declaring exactly which bands it serves.

    A task ONLY serves its declared bands — the guarantee that lets the
    differentiator refuse a cross-band assignment."""

    task_id: str
    outcome_id: str
    bands: Tuple[MasteryBand, ...]
    scaffold_level: int = 0

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("DifferentiatedTask.task_id is required.")
        if not self.outcome_id:
            raise ValueError("DifferentiatedTask.outcome_id is required (opaque token).")

    def serves(self, band: MasteryBand) -> bool:
        return band in self.bands


@dataclass(frozen=True)
class DifferentiationPlan:
    """The differentiation for one outcome: each opaque learner id mapped to its
    band and the band-appropriate task (or None when no task serves the band).

    A recommendation a teacher reviews."""

    outcome_id: str
    subject_uuid: str
    bands: Dict[str, MasteryBand]
    assignments: Dict[str, Optional[DifferentiatedTask]]

    def band_of(self, canonical_uuid: str) -> Optional[MasteryBand]:
        return self.bands.get(canonical_uuid)

    def task_of(self, canonical_uuid: str) -> Optional[DifferentiatedTask]:
        return self.assignments.get(canonical_uuid)

    @property
    def learner_count(self) -> int:
        return len(self.bands)

    def respects_bands(self) -> bool:
        """True when every assigned task serves the learner's own band. An
        unassigned learner is vacuously fine — no wrong assignment exists."""
        for uuid, task in self.assignments.items():
            if task is None:
                continue
            if not task.serves(self.bands[uuid]):
                return False
        return True


class Differentiator:
    """Assigns each learner a band-appropriate task for one outcome.

    Respects the mastery bands: a learner is only matched to a task whose declared
    bands include the learner's own band; otherwise the learner is left
    unassigned (never mis-pitched). Readings for OTHER outcomes are ignored.
    """

    def __init__(self, event_log: Optional[EventLog] = None) -> None:
        self._events = event_log

    def assign(
        self,
        outcome_id: str,
        subject_uuid: str,
        readiness: Sequence[LearnerReadiness],
        task_bank: Sequence[DifferentiatedTask],
    ) -> DifferentiationPlan:
        relevant_tasks = [t for t in task_bank if t.outcome_id == outcome_id]

        bands: Dict[str, MasteryBand] = {}
        assignments: Dict[str, Optional[DifferentiatedTask]] = {}

        for r in readiness:
            if r.outcome_id != outcome_id:
                continue  # readings for other outcomes are ignored
            band = r.band
            bands[r.canonical_uuid] = band
            # Match the lowest-scaffold task that serves this band, deterministic.
            match: Optional[DifferentiatedTask] = None
            for task in sorted(relevant_tasks, key=lambda t: (t.scaffold_level, t.task_id)):
                if task.serves(band):
                    match = task
                    break
            assignments[r.canonical_uuid] = match

        plan = DifferentiationPlan(
            outcome_id=outcome_id,
            subject_uuid=subject_uuid,
            bands=bands,
            assignments=assignments,
        )

        if self._events is not None:
            self._events.emit(
                EventType.DIFFERENTIATION_GENERATED,
                subject_uuid=subject_uuid,
                payload={
                    "outcome_id": outcome_id,
                    "learner_count": plan.learner_count,
                    "respects_bands": plan.respects_bands(),
                },
            )
        return plan
