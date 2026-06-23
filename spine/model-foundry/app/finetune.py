"""The fine-tune / DISTILLATION runner (spine A4 — Track 2).

Distil from a Track-1 frontier TEACHER into a small Track-2 edge STUDENT over a
versioned dataset. The actual GPU training is an INJECTED BACKEND reached by a
named secret (INVARIANT 4):

* ``clss.modelfoundry.dev.training_endpoint`` (CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT)
* ``clss.modelfoundry.dev.training_key``      (CLSS_MODELFOUNDRY_DEV_TRAINING_KEY)

With NO backend configured, the runner returns a clearly-marked ``no-compute``
plan — the recipe + dataset ref + expected artifacts — WITHOUT fabricating a
model. This is the "press go when compute is attached" seam: the whole loop is
real and tested; only the GPU step is deferred.

INVARIANT 11 — the student is always a TRACK 2 model. The teacher is a Track 1
label only (distillation source); the two tracks are never conflated and no
Track 1 credential is read here. INVARIANT 4 — the training key is read by NAME,
never returned in a result object, never logged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from .config import (
    TRAINING_ENDPOINT_SECRET_NAME,
    TRAINING_KEY_SECRET_NAME,
    Settings,
    get_settings,
)
from .dataset import Dataset

TRACK_ID = 2  # the foundry only ever produces Track 2 students


@dataclass(frozen=True)
class DistillRecipe:
    """The distillation recipe — a reproducible description of the run.

    Carries NO secrets. ``teacher_label`` is a Track 1 frontier model label
    (distillation source only); ``student_label`` is the Track 2 edge student.
    """

    teacher_label: str
    student_label: str
    objective: str = "distillation"
    epochs: int = 3
    batch_size: int = 16
    learning_rate: float = 5e-5
    max_seq_len: int = 1024
    temperature: float = 2.0
    notes: str = ""


@dataclass(frozen=True)
class ExpectedArtifacts:
    """What a successful run is expected to produce (named, not fabricated)."""

    candidate_id: str
    weights_uri_template: str
    scorecard_required: bool = True
    track: int = TRACK_ID


@dataclass(frozen=True)
class NoComputePlan:
    """Returned when no training backend is configured. NOT a model.

    A clearly-marked plan a human (or CI, once compute is attached) can execute.
    ``status`` is always ``"no-compute"`` so callers can never mistake it for a
    trained candidate.
    """

    status: str
    reason: str
    recipe: DistillRecipe
    dataset_id: str
    dataset_content_hash: str
    expected_artifacts: ExpectedArtifacts
    required_secret_names: tuple[str, ...]
    track: int = TRACK_ID


@dataclass(frozen=True)
class TrainedCandidate:
    """The result of a REAL backend run. Produced only by an injected backend;
    the runner never constructs this itself without a backend."""

    status: str
    candidate_id: str
    student_label: str
    weights_uri: str
    dataset_id: str
    dataset_content_hash: str
    recipe: DistillRecipe
    track: int = TRACK_ID
    backend_run_id: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


class TrainingBackend(Protocol):
    """The injected GPU training seam.

    A real implementation submits the distillation job to the configured
    endpoint using the raw key (which it receives here and NEVER returns or
    logs) and returns a :class:`TrainedCandidate`. With no backend implementing
    this Protocol wired, the runner degrades to a no-compute plan.
    """

    def train(
        self,
        *,
        endpoint: str,
        raw_key: str,
        recipe: DistillRecipe,
        dataset: Dataset,
    ) -> TrainedCandidate:
        ...


class FineTuneRunner:
    """Runs (or plans) a distillation. Degrades to a no-compute plan by default."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        backend: TrainingBackend | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._backend = backend

    def run(self, *, recipe: DistillRecipe, dataset: Dataset) -> NoComputePlan | TrainedCandidate:
        """Distil ``recipe.teacher_label`` -> ``recipe.student_label`` over the
        dataset. Returns a TrainedCandidate ONLY when both a backend is injected
        AND the training secrets are configured; otherwise a NoComputePlan."""
        candidate_id = f"cand-{dataset.manifest.content_hash[:12]}-{uuid4().hex[:8]}"
        expected = ExpectedArtifacts(
            candidate_id=candidate_id,
            weights_uri_template=(
                f"{{training_endpoint}}/artifacts/{candidate_id}/student.safetensors"
            ),
        )

        configured = self._settings.training_configured()
        if not configured or self._backend is None:
            reason = (
                "no training backend injected"
                if self._backend is None
                else "training endpoint/key not configured"
            )
            return NoComputePlan(
                status="no-compute",
                reason=reason,
                recipe=recipe,
                dataset_id=dataset.manifest.dataset_id,
                dataset_content_hash=dataset.manifest.content_hash,
                expected_artifacts=expected,
                required_secret_names=(
                    TRAINING_ENDPOINT_SECRET_NAME,
                    TRAINING_KEY_SECRET_NAME,
                ),
            )

        # Backend present AND configured: hand the raw key to the seam only.
        # The key is never placed in any returned object or log line.
        result = self._backend.train(
            endpoint=self._settings.training_endpoint,  # type: ignore[arg-type]
            raw_key=self._settings.training_key,  # type: ignore[arg-type]
            recipe=recipe,
            dataset=dataset,
        )
        # Enforce the Track 2 invariant on whatever the backend returns.
        if result.track != TRACK_ID:
            raise ValueError("training backend returned a non-Track-2 candidate")
        return result
