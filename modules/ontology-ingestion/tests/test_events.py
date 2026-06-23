"""Ontology lifecycle events: append-only, opaque-only, degrade offline, and the
edge-confirmed event is approval-gated (never auto-fires)."""

from __future__ import annotations

import pytest

from app.config import OntologySettings
from app.events import (
    EventEmitter,
    build_edge_confirmed_payload,
    build_edge_proposed_payload,
    build_equivalence_mapped_payload,
    build_node_ingested_payload,
)

CANON = "9999aaaa-0000-4000-8000-000000000001"
CONSENT = "cccccccc-0000-4000-8000-000000000003"
STEWARD = "5ee0a000-0000-4000-8000-000000000009"
T1 = "70910000-0000-4000-8000-000000000301"
T2 = "70910000-0000-4000-8000-000000000302"


def test_emitter_degrades_to_in_memory_sink_with_no_gateway():
    emitter = EventEmitter(OntologySettings())
    assert emitter.degraded is True
    assert "in-memory" in emitter.sink_label
    assert "clss.ontology.dev.gateway_url" in emitter.sink_label


def test_edge_proposed_event_records_unconfirmed():
    payload = build_edge_proposed_payload(
        edge_id="e1", from_topic_id=T1, to_topic_id=T2,
        kind="soft", rationale="ordering evidence", confidence=0.55,
    )
    # A proposed edge event ALWAYS records confirmed = False.
    assert payload["confirmed"] is False
    assert payload["rationale"] == "ordering evidence"


def test_edge_confirmed_requires_a_steward_ref():
    with pytest.raises(PermissionError):
        build_edge_confirmed_payload(
            edge_id="e1", from_topic_id=T1, to_topic_id=T2, confirmed_by=""
        )
    payload = build_edge_confirmed_payload(
        edge_id="e1", from_topic_id=T1, to_topic_id=T2, confirmed_by=STEWARD
    )
    assert payload["confirmed"] is True
    assert payload["confirmed_by"] == STEWARD


def test_node_ingested_event_is_draft_and_carries_board_label():
    emitter = EventEmitter(OntologySettings())
    result = emitter.emit_node_ingested(
        canonical_uuid=CANON, consent_ref=CONSENT,
        node_id="n1", node_kind="topic", board_code="example-state-board",
        source_ref="doc-1", extraction_confidence=0.42,
    )
    env = result.envelope
    assert result.delivered is False                   # local-only, degraded.
    assert env["type"] == "ontology.node_ingested"
    assert env["purpose"] == "operations"
    assert env["payload"]["draft"] is True             # never trusted on ingest.
    assert env["payload"]["board_code"] == "example-state-board"
    assert emitter.buffered() == [env]                 # append-only.


def test_equivalence_event_is_board_agnostic():
    payload = build_equivalence_mapped_payload(
        equivalence_id="q1", node_id="n1", node_kind="topic",
        equivalent_board_code="another-example-board",
        equivalent_label="Euclidean algorithm", confidence=0.95,
    )
    assert payload["equivalent_board_code"] == "another-example-board"
    assert payload["confidence"] == 0.95


def test_appends_are_immutable_across_emits():
    emitter = EventEmitter(OntologySettings())
    emitter.emit_edge_proposed(
        canonical_uuid=CANON, consent_ref=CONSENT, edge_id="e1",
        from_topic_id=T1, to_topic_id=T2, kind="soft",
        rationale="x", confidence=0.5,
    )
    first = emitter.buffered()
    emitter.emit_edge_confirmed(
        canonical_uuid=CANON, consent_ref=CONSENT, edge_id="e1",
        from_topic_id=T1, to_topic_id=T2, confirmed_by=STEWARD,
    )
    assert len(first) == 1
    assert len(emitter.buffered()) == 2


def test_no_pii_in_any_payload():
    payload = build_node_ingested_payload(
        node_id="n1", node_kind="topic", board_code="b", source_ref="s",
    )
    forbidden = {"name", "email", "phone", "first_name", "last_name", "dob"}
    assert not (forbidden & set(payload.keys()))
