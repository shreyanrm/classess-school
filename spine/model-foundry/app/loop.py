"""The closed continuous-learning loop (spine A4 — Track 2).

Pure orchestration over the foundry modules:

    observe(events)
      -> capture            (events -> learning signals, consent-stamped)
      -> consent-gate       (keep only admissible — INVARIANT 6)
      -> curate             (safety + verify + balance — INVARIANT 7)
      -> dataset            (versioned, deduped, PII-scrubbed, provenance)
      -> (train backend)    (distill teacher -> Track 2 student; no-compute by default)
      -> eval               (scorecard vs incumbent)
      -> require_approval    (permission ladder — INVARIANT 8; never auto-promotes)
      -> promote            (only on explicit human approval -> Track 2 slot)
      -> serve(Track 2)      (the promoted student fills the reserved slot)
      -> observe outcomes    (new events feed the next turn)

The loop is IDEMPOTENT and REPLAYABLE: the dataset content hash is a pure
function of the admissible signals, so re-running ``observe`` over the same
events yields the same dataset id and the same candidate plan. Promotion is the
only side-effecting, human-gated step, and it is never taken automatically.

This module imports only the foundry's own modules and the AI fabric is reached
only through injected callables (a verifier, a predictor) so it never modifies
ai-fabric.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from . import events as fevents
from .capture import LearningSignal, SignalCapture
from .consent_gate import ConsentGate
from .curate import CurationReport, Curator, Verifier
from .dataset import Dataset, DatasetBuilder
from .eval import Comparison, Evaluator, Predictor, SafetyProbe, Scorecard, compare
from .finetune import DistillRecipe, FineTuneRunner, NoComputePlan, TrainedCandidate
from .registry import ModelRegistry, PromotionDecision, PromotionRecord


@dataclass(frozen=True)
class TurnResult:
    """The result of one loop turn up to (not including) promotion.

    Promotion is intentionally NOT part of a turn: it requires an explicit human
    approval call. ``promotion`` holds the requires-approval decision the loop
    surfaces for a human to act on.
    """

    signals: list[LearningSignal]
    admissible_signals: list[LearningSignal]
    curation: CurationReport
    dataset: Dataset
    plan: NoComputePlan | TrainedCandidate
    candidate_id: str
    scorecard: Scorecard | None
    comparison: Comparison | None
    promotion: PromotionDecision | None


class ContinuousLearningLoop:
    """Orchestrates one or many turns. Holds the registry across turns."""

    def __init__(
        self,
        *,
        consent_gate: ConsentGate,
        registry: ModelRegistry | None = None,
        runner: FineTuneRunner | None = None,
        curator: Curator | None = None,
        evaluator: Evaluator | None = None,
        builder: DatasetBuilder | None = None,
        sink: fevents.EventSink | None = None,
    ) -> None:
        self._gate = consent_gate
        self._capture = SignalCapture(consent_gate)
        self._registry = registry or ModelRegistry()
        self._runner = runner or FineTuneRunner()
        self._curator = curator or Curator()
        self._evaluator = evaluator or Evaluator()
        self._builder = builder or DatasetBuilder()
        self._sink = sink or (lambda _e: None)

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    def observe(
        self,
        *,
        events: list[dict],
        recipe: DistillRecipe,
        incumbent_scorecard: Scorecard | None = None,
        candidate_predictor: Predictor | None = None,
        safety_probes: list[SafetyProbe] | None = None,
    ) -> TurnResult:
        """Run one turn: events -> ... -> a promotion decision (never promotes).

        ``candidate_predictor`` is the candidate model under eval, supplied by
        the caller (e.g. a TrainedCandidate's served predictor, or a stub when
        running the loop with no compute). With none supplied, eval is skipped
        and no promotion can be requested — the turn stops at the dataset/plan.
        """
        # observe -> capture
        signals = self._capture.capture_stream(events)
        # consent-gate (keep only admissible — INVARIANT 6)
        admissible = [s for s in signals if s.admissible]
        # curate (safety + verify + balance — INVARIANT 7)
        clean, curation = self._curator.curate(admissible)
        # dataset (versioned, deduped, PII-scrubbed, provenance)
        dataset = self._builder.build(clean, notes=f"distill->{recipe.student_label}")
        self._sink(
            fevents.dataset_built(
                dataset_id=dataset.manifest.dataset_id,
                content_hash=dataset.manifest.content_hash,
                total_examples=dataset.manifest.total_examples,
                split_counts=dataset.manifest.split_counts,
                per_class_counts=dataset.manifest.per_class_counts,
                consent_ref_count=len(dataset.manifest.consent_refs),
            )
        )

        # train backend (distill; no-compute plan by default — never fabricates)
        plan = self._runner.run(recipe=recipe, dataset=dataset)
        candidate_id = (
            plan.candidate_id
            if isinstance(plan, TrainedCandidate)
            else plan.expected_artifacts.candidate_id
        )

        # Register the candidate (registered state) regardless of compute, so the
        # lifecycle is tracked and replayable.
        if candidate_id not in self._registry_ids():
            self._registry.register(
                candidate_id=candidate_id,
                student_label=recipe.student_label,
                dataset_id=dataset.manifest.dataset_id,
                dataset_content_hash=dataset.manifest.content_hash,
            )

        scorecard: Scorecard | None = None
        comparison: Comparison | None = None
        promotion: PromotionDecision | None = None

        # eval -> require_approval (only if there is a candidate model to score)
        if candidate_predictor is not None:
            scorecard = self._evaluator.score(
                model_label=recipe.student_label,
                predictor=candidate_predictor,
                dataset=dataset,
                safety_probes=safety_probes,
            )
            comparison = compare(scorecard, incumbent_scorecard)
            self._registry.attach_eval(
                candidate_id=candidate_id, scorecard=scorecard, comparison=comparison
            )
            self._sink(
                fevents.candidate_evaluated(
                    candidate_id=candidate_id,
                    dataset_id=dataset.manifest.dataset_id,
                    composite=scorecard.composite,
                    candidate_better=comparison.candidate_better,
                    summary=comparison.summary,
                )
            )
            # require_approval — NEVER auto-promotes (INVARIANT 8).
            promotion = self._registry.request_promotion(candidate_id=candidate_id)
            self._sink(
                fevents.promotion_requested(
                    candidate_id=candidate_id,
                    requires_approval=promotion.requires_approval,
                    eligible=promotion.eligible,
                    rung=promotion.rung,
                    reason=promotion.reason,
                )
            )

        return TurnResult(
            signals=signals,
            admissible_signals=admissible,
            curation=curation,
            dataset=dataset,
            plan=plan,
            candidate_id=candidate_id,
            scorecard=scorecard,
            comparison=comparison,
            promotion=promotion,
        )

    def approve_and_promote(
        self, *, candidate_id: str, approved_by: UUID
    ) -> PromotionRecord:
        """The ONLY way a candidate advances into the Track 2 serving slot.

        Requires an explicit human approver. Emits the ``promoted`` event. This
        is the single human-gated, side-effecting step of the loop.
        """
        record = self._registry.approve_promotion(
            candidate_id=candidate_id, approved_by=approved_by
        )
        self._sink(
            fevents.promoted(
                candidate_id=record.candidate_id,
                student_label=record.student_label,
                approved_by=record.approved_by,
                approved_at=record.approved_at,
                previous_active=record.previous_active,
            )
        )
        return record

    def serving_track2(self) -> str | None:
        """The candidate currently serving learners in the Track 2 slot."""
        return self._registry.active_track2()

    def _registry_ids(self) -> set[str]:
        try:
            # No public list; probe via history + active is insufficient, so we
            # track by attempting a get. Simpler: maintain via private dict.
            return set(self._registry._candidates.keys())  # noqa: SLF001
        except AttributeError:  # pragma: no cover
            return set()
