"""Foundry events are PII-free, immutable, and carry no learner identity."""

from __future__ import annotations

import dataclasses

import pytest

from app import events as fevents

from .conftest import APPROVER, NOW


def test_dataset_built_event_shape():
    e = fevents.dataset_built(
        dataset_id="ds-1",
        content_hash="abc",
        total_examples=10,
        split_counts={"train": 8, "val": 1, "test": 1},
        per_class_counts={"x": 10},
        consent_ref_count=3,
        emitted_at=NOW,
    )
    assert e.type == "modelfoundry.dataset-built"
    assert e.payload["content_hash"] == "abc"
    # No canonical_uuid / PII on a pipeline event.
    assert "canonical_uuid" not in e.payload


def test_events_are_immutable():
    e = fevents.candidate_evaluated(
        candidate_id="c1", dataset_id="ds-1", composite=0.9, candidate_better=True, summary="ok", emitted_at=NOW
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.type = "x"  # type: ignore[misc]


def test_promoted_event_records_who_when():
    e = fevents.promoted(
        candidate_id="c1",
        student_label="edge-v1",
        approved_by=APPROVER,
        approved_at=NOW,
        previous_active=None,
        emitted_at=NOW,
    )
    assert e.payload["approved_by"] == str(APPROVER)
    assert e.payload["track"] == 2


def test_collecting_sink_collects():
    sink = fevents.CollectingSink()
    sink(fevents.promotion_requested(candidate_id="c1", requires_approval=True, eligible=True, rung="execute-with-permission", reason="ok", emitted_at=NOW))
    assert sink.types() == ["modelfoundry.promotion-requested"]
