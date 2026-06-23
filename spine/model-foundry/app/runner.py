"""Press-go runner for the foundry pipeline (spine A4 — Track 2).

The single executable entrypoint that runs the whole loop up to the human-gated
promotion step, then reports READINESS:

* with NO compute attached -> it captures + gates + curates signals, builds the
  versioned PII-free dataset, registers the candidate, evaluates a supplied
  predictor (if any), and reports a ``no-compute`` readiness plan — never a model;
* with a TrainingBackend + the named training secrets attached -> the SAME call
  trains a real candidate via the injected backend and reports it.

It is a thin, dependency-free wrapper over :class:`ContinuousLearningLoop` so the
operational "run it" command and the in-process loop share one code path. Run as
``python -m app.runner`` for a self-contained offline readiness report (no
network, no training, no key required).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .finetune import NoComputePlan, TrainedCandidate
from .loop import ContinuousLearningLoop, TurnResult


@dataclass(frozen=True)
class ReadinessReport:
    """A press-go readiness summary for one run. PII-free; counts + statuses only."""

    compute_attached: bool
    teacher_available: bool
    dataset_id: str
    dataset_content_hash: str
    total_examples: int
    per_class_counts: dict[str, int]
    plan_status: str  # "no-compute" or "trained"
    candidate_id: str
    eval_ran: bool
    gate_passed: bool | None
    gate_failures: tuple[str, ...]
    promotion_eligible: bool | None
    promotion_requires_approval: bool | None
    next_action: str

    def to_dict(self) -> dict:
        return {
            "compute_attached": self.compute_attached,
            "teacher_available": self.teacher_available,
            "dataset_id": self.dataset_id,
            "dataset_content_hash": self.dataset_content_hash,
            "total_examples": self.total_examples,
            "per_class_counts": self.per_class_counts,
            "plan_status": self.plan_status,
            "candidate_id": self.candidate_id,
            "eval_ran": self.eval_ran,
            "gate_passed": self.gate_passed,
            "gate_failures": list(self.gate_failures),
            "promotion_eligible": self.promotion_eligible,
            "promotion_requires_approval": self.promotion_requires_approval,
            "next_action": self.next_action,
        }


def readiness_from_turn(turn: TurnResult) -> ReadinessReport:
    """Summarise a completed loop turn into a press-go readiness report."""
    trained = isinstance(turn.plan, TrainedCandidate)
    teacher_available = bool(turn.teacher and turn.teacher.available)

    gate_passed: bool | None = None
    gate_failures: tuple[str, ...] = ()
    promotion_eligible: bool | None = None
    requires_approval: bool | None = None

    if turn.promotion is not None:
        promotion_eligible = turn.promotion.eligible
        requires_approval = turn.promotion.requires_approval

    # Reach into the registry record for the gate result, if eval ran.
    if turn.scorecard is not None:
        gate_passed = turn.comparison is not None and turn.comparison.candidate_better

    if not trained:
        next_action = (
            "Attach a TrainingBackend + set the training secrets, then re-run to "
            "train; the dataset is built and the candidate is registered."
        )
    elif promotion_eligible:
        next_action = (
            "Eval clears the bar — a human must explicitly approve promotion into "
            "the Track 2 slot (approve_and_promote)."
        )
    elif turn.scorecard is not None:
        next_action = "Eval did not clear the bar; candidate is not promotable."
    else:
        next_action = "Supply a candidate predictor to evaluate the candidate."

    return ReadinessReport(
        compute_attached=trained,
        teacher_available=teacher_available,
        dataset_id=turn.dataset.manifest.dataset_id,
        dataset_content_hash=turn.dataset.manifest.content_hash,
        total_examples=turn.dataset.manifest.total_examples,
        per_class_counts=dict(turn.dataset.manifest.per_class_counts),
        plan_status="trained" if trained else "no-compute",
        candidate_id=turn.candidate_id,
        eval_ran=turn.scorecard is not None,
        gate_passed=gate_passed,
        gate_failures=gate_failures,
        promotion_eligible=promotion_eligible,
        promotion_requires_approval=requires_approval,
        next_action=next_action,
    )


def run_once(loop: ContinuousLearningLoop, **observe_kwargs) -> tuple[TurnResult, ReadinessReport]:
    """Run one press-go turn and return (turn, readiness). Never promotes."""
    turn = loop.observe(**observe_kwargs)
    return turn, readiness_from_turn(turn)


def _demo() -> ReadinessReport:
    """A self-contained, offline demonstration run (no network, no key).

    Captures a tiny synthetic, consent-stamped, PII-free event stream, builds a
    dataset, and reports readiness with no compute attached. Imported lazily-free
    so ``python -m app.runner`` works from the package root.
    """
    from datetime import datetime, timezone
    from uuid import UUID

    from .config import get_settings
    from .consent_gate import MODEL_IMPROVEMENT_SCOPE, ConsentGate, ConsentRecord
    from .finetune import DistillRecipe, FineTuneRunner

    learner = UUID("aaaaaaaa-0000-4000-8000-000000000001")
    consent = UUID("c0000000-0000-4000-8000-000000000001")
    topic = UUID("70910000-0000-4000-8000-000000000301")
    now = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)

    gate = ConsentGate(
        [ConsentRecord(consent, learner, "adult", MODEL_IMPROVEMENT_SCOPE)]
    )
    events = [
        {
            "event_id": UUID(f"e0e00000-0000-4000-8000-{i:012d}"),
            "occurred_at": now,
            "canonical_uuid": learner,
            "consent_ref": consent,
            "type": "attempt.recorded",
            "payload": {
                "attempt_id": str(i),
                "ontology": {"topic_id": str(topic)},
                "mode": "independent",
                "assistance_level": "Independent",
                "correct": True,
                "difficulty": round(0.4 + i * 0.05, 2),  # distinct inputs, not contradictory
            },
        }
        for i in range(1, 11)
    ]
    loop = ContinuousLearningLoop(
        consent_gate=gate,
        runner=FineTuneRunner(settings=get_settings(env={}), backend=None),
    )
    recipe = DistillRecipe(teacher_label="track1-frontier", student_label="edge-student-v1")
    _turn, report = run_once(loop, events=events, recipe=recipe)
    return report


def main() -> int:
    report = _demo()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
