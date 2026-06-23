"""xAPI / Caliper statements round-trip through the internal shape with no PII.

The round-trip: internal -> external -> internal preserves verb, object, result
and the OPAQUE actor key, and the external form never contains an mbox/email.
Inbound real-world statements (with mbox/email actors) reduce to opaque refs.
"""

from __future__ import annotations

import json

from app import CanonicalRef, LearningActivityStatement, Standard, Verb
from app.adapters import CaliperAdapter, XAPIAdapter
from app.adapters.xapi import ACCOUNT_HOMEPAGE


def _opaque_actor() -> CanonicalRef:
    return CanonicalRef(
        source_standard=Standard.XAPI,
        source_key="xapi:deadbeef",
        canonical_uuid="11111111-2222-3333-4444-555555555555",
    )


# ---------------------------------------------------------------------------
# xAPI
# ---------------------------------------------------------------------------
def test_xapi_inbound_mbox_actor_reduced_to_opaque_key():
    adapter = XAPIAdapter("xapi:test")
    stmt = adapter.to_internal({
        "actor": {"objectType": "Agent", "mbox": "mailto:asha@example.com"},
        "verb": {"id": "http://adlnet.gov/expapi/verbs/answered"},
        "object": {"objectType": "Activity", "id": "act:q-1"},
        "result": {"success": True, "score": {"scaled": 0.8}},
        "timestamp": "2026-06-22T10:00:00Z",
    })
    assert stmt.verb is Verb.ANSWERED
    assert stmt.object_id == "act:q-1"
    assert stmt.result_success is True
    assert stmt.result_score_scaled == 0.8
    # the email never survives onto the ref
    assert "asha@example.com" not in stmt.actor.source_key
    assert stmt.actor.canonical_uuid is None  # unresolved offline


def test_xapi_roundtrip_preserves_payload_and_hides_pii():
    adapter = XAPIAdapter("xapi:test")
    original = LearningActivityStatement(
        actor=_opaque_actor(),
        verb=Verb.SCORED,
        object_id="act:assessment-9",
        result_success=True,
        result_score_scaled=0.95,
        result_completion=True,
        context_activity_ids=["act:course-1"],
    )
    xapi = adapter.from_internal(original)

    # Outbound actor is an opaque account, never an mbox/email.
    assert "mbox" not in xapi["actor"]
    assert xapi["actor"]["account"]["homePage"] == ACCOUNT_HOMEPAGE
    assert xapi["actor"]["account"]["name"] == original.actor.canonical_uuid
    assert "@" not in json.dumps(xapi)  # no email anywhere

    back = adapter.to_internal(xapi)
    assert back.verb is Verb.SCORED
    assert back.object_id == "act:assessment-9"
    assert back.result_score_scaled == 0.95
    assert back.result_completion is True
    assert back.context_activity_ids == ["act:course-1"]
    # actor key preserved through the round-trip
    assert back.actor.source_key == _derived(adapter, original.actor.canonical_uuid)


def _derived(adapter, account_name):
    # The outbound account name becomes the next inbound external id; assert the
    # adapter reproduces a stable key for it.
    from app.mapping import derive_source_key
    return derive_source_key(Standard.XAPI, f"{ACCOUNT_HOMEPAGE}|{account_name}")


# ---------------------------------------------------------------------------
# Caliper
# ---------------------------------------------------------------------------
def test_caliper_inbound_reduces_actor_and_computes_score():
    adapter = CaliperAdapter("caliper:test")
    stmt = adapter.to_internal({
        "@context": "http://purl.imsglobal.org/ctx/caliper/v1p2",
        "type": "GradeEvent",
        "actor": {"id": "https://lms.example.com/users/lee", "type": "Person"},
        "action": "Graded",
        "object": {"id": "https://lms.example.com/assess/1", "type": "Assessment"},
        "generated": {"type": "Score", "scoreGiven": 8, "maxScore": 10},
        "eventTime": "2026-06-22T11:00:00Z",
    })
    assert stmt.verb is Verb.SCORED
    assert stmt.object_id == "https://lms.example.com/assess/1"
    assert abs(stmt.result_score_scaled - 0.8) < 1e-9
    assert "lee" not in stmt.actor.source_key.split(":", 1)[1]


def test_caliper_roundtrip_preserves_verb_object_and_opaque_actor():
    adapter = CaliperAdapter("caliper:test")
    original = LearningActivityStatement(
        actor=CanonicalRef(Standard.CALIPER, "caliper:abc123", "uuid-xyz"),
        verb=Verb.COMPLETED,
        object_id="urn:resource:42",
    )
    event = adapter.from_internal(original)
    assert event["action"] == "Completed"
    assert event["object"]["id"] == "urn:resource:42"
    assert event["actor"]["id"].endswith("uuid-xyz")

    back = adapter.to_internal(event)
    assert back.verb is Verb.COMPLETED
    assert back.object_id == "urn:resource:42"
