"""Fine-tune / distillation: no-compute by default, real backend when injected."""

from __future__ import annotations

import pytest

from app.capture import TASK_MASTERY_PREDICT, LearningSignal
from app.config import (
    TRAINING_ENDPOINT_SECRET_NAME,
    TRAINING_KEY_SECRET_NAME,
    get_settings,
)
from app.dataset import Dataset, DatasetBuilder
from app.finetune import (
    DistillRecipe,
    FineTuneRunner,
    NoComputePlan,
    TrainedCandidate,
)

from .conftest import ADULT, CONSENT_ADULT


def _dataset() -> Dataset:
    sigs = [
        LearningSignal(
            signal_id=f"s{i}",
            canonical_uuid=ADULT,
            task_class=TASK_MASTERY_PREDICT,
            input=f"i{i}",
            output="correct",
            reward=0.95,
            consent_ref=CONSENT_ADULT,
            age_tier="adult",
            admissible=True,
        )
        for i in range(5)
    ]
    return DatasetBuilder().build(sigs)


RECIPE = DistillRecipe(teacher_label="track1-frontier", student_label="edge-student-v1")


def test_no_backend_degrades_to_no_compute_plan():
    runner = FineTuneRunner(settings=get_settings(env={}), backend=None)
    result = runner.run(recipe=RECIPE, dataset=_dataset())
    assert isinstance(result, NoComputePlan)
    assert result.status == "no-compute"
    assert result.track == 2
    assert TRAINING_ENDPOINT_SECRET_NAME in result.required_secret_names
    assert TRAINING_KEY_SECRET_NAME in result.required_secret_names
    # The plan references the dataset and expected artifacts WITHOUT a model.
    assert result.dataset_content_hash
    assert result.expected_artifacts.candidate_id
    assert "no training backend" in result.reason


def test_partial_secrets_still_no_compute():
    env = {"CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT": "https://x"}  # no key
    runner = FineTuneRunner(settings=get_settings(env=env), backend=_StubBackend())
    result = runner.run(recipe=RECIPE, dataset=_dataset())
    assert isinstance(result, NoComputePlan)
    assert "not configured" in result.reason


def test_no_plan_fabricates_weights():
    runner = FineTuneRunner(settings=get_settings(env={}), backend=None)
    result = runner.run(recipe=RECIPE, dataset=_dataset())
    assert isinstance(result, NoComputePlan)
    # Only a TEMPLATE uri, never a concrete artifact.
    assert "{training_endpoint}" in result.expected_artifacts.weights_uri_template


class _StubBackend:
    """A fake injected backend — only used when secrets are configured."""

    def __init__(self):
        self.seen_key = None

    def train(self, *, endpoint, raw_key, recipe, dataset):
        self.seen_key = raw_key  # backend receives the raw key (and only here)
        return TrainedCandidate(
            status="trained",
            candidate_id="cand-stub",
            student_label=recipe.student_label,
            weights_uri=f"{endpoint}/artifacts/cand-stub/student.safetensors",
            dataset_id=dataset.manifest.dataset_id,
            dataset_content_hash=dataset.manifest.content_hash,
            recipe=recipe,
            track=2,
            backend_run_id="run-1",
        )


def test_configured_backend_trains():
    env = {
        "CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT": "https://train.example",
        "CLSS_MODELFOUNDRY_DEV_TRAINING_KEY": "secret-value",
    }
    backend = _StubBackend()
    runner = FineTuneRunner(settings=get_settings(env=env), backend=backend)
    result = runner.run(recipe=RECIPE, dataset=_dataset())
    assert isinstance(result, TrainedCandidate)
    assert result.track == 2
    assert backend.seen_key == "secret-value"  # key reached the seam
    # The raw key is NEVER in the returned object.
    assert "secret-value" not in repr(result)


def test_backend_returning_non_track2_rejected():
    env = {
        "CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT": "https://train.example",
        "CLSS_MODELFOUNDRY_DEV_TRAINING_KEY": "secret-value",
    }

    class _BadBackend(_StubBackend):
        def train(self, **kw):
            tc = super().train(**kw)
            return TrainedCandidate(**{**tc.__dict__, "track": 1})

    runner = FineTuneRunner(settings=get_settings(env=env), backend=_BadBackend())
    with pytest.raises(ValueError):
        runner.run(recipe=RECIPE, dataset=_dataset())
