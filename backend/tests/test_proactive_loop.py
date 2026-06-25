"""The proactive loop + permission ladder, wired through the deployable.

Proves the Wave-1 proactive-loop wiring end to end, fully offline (Starlette
TestClient — no network, no DB, no secret):

  1. CONSEQUENTIAL OP REQUIRES APPROVAL
     An admitted route that is CONSEQUENTIAL (the EXECUTE rung the consequential
     verbs grade/send/publish/delete/charge route onto) is REFUSED at the wall
     unless an X-Approval-Token is presented — APPROVAL_REQUIRED (403). It can
     never auto-fire (INVARIANT 8). With the token it is admitted and dispatched.

  2. recommend -> approve -> execute EMITS ALL FOUR EVENTS
     The loop, driven through the capability door, persists the four workflow
     events to the event store: recommendation.created (recommend),
     recommendation.actioned + approval.given (approve), action.executed (execute
     AFTER the human approval). Execute BEFORE approval emits nothing (the ladder
     holds).

  3. INTELLIGENCE /read SERVED BY THE SPINE
     POST /v1/intelligence/read is actually SERVED (the in-process mount the
     gateway forwards to), returning the governed view computed by replaying the
     event store through the ONE engine — not a glue-pending stub.

CONFIDENTIALITY: every id is an opaque canonical ref. No PII, no names, no board,
no real pricing.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from backend import intelligence_views, workflow_app
from backend.main import app

client = TestClient(app)

_TEACHER = "11111111-1111-4111-8111-111111111111"
_DECIDER = "22222222-2222-4222-8222-222222222222"
_CONSENT = "cccccccc-0000-4000-8000-000000000003"
_STUDENT_A = "a0000000-0000-4000-8000-00000000000a"
_TOPIC = "70000000-0000-4000-8000-000000000001"


def _dev_token(canonical_uuid: str, role: str = "teacher") -> str:
    claims = {
        "canonical_uuid": canonical_uuid,
        "app": "school",
        "memberships": [{"app": "school", "role": role, "scope": "inst-1"}],
    }
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "DEV-UNSIGNED." + body


def _auth(token: str, *, approval: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if approval is not None:
        headers["X-Approval-Token"] = approval
    return headers


# --------------------------------------------------------------------------- #
# 1. A consequential op is REFUSED without approval, ADMITTED with it.
# --------------------------------------------------------------------------- #
def test_consequential_op_requires_approval_at_the_wall():
    """The EXECUTE rung is registered consequential -> the wall forces an
    X-Approval-Token (step 8). Without one the route is DENIED (403,
    approval_required) and never reaches a module; with one it is admitted."""
    token = _dev_token(_TEACHER)

    # Seed a recommendation so execute has something to act on (recommend without
    # a cross-context purpose -> the consent gate is not triggered).
    rec = client.post(
        "/capabilities/intelligence-views/recommend",
        headers=_auth(token),
        json={"effect_verb": "send", "owner_ref": _TEACHER, "consent_ref": _CONSENT},
    )
    assert rec.status_code == 200, rec.text
    rid = rec.json()["result"]["recommendation_id"]

    # EXECUTE without an approval token -> the wall denies (consequential rung).
    denied = client.post(
        "/capabilities/intelligence-views/execute",
        headers=_auth(token),
        json={"recommendation_id": rid},
    )
    assert denied.status_code == 403
    assert denied.json()["reason"] == "approval_required"
    assert "result" not in denied.json()  # never reached the module

    # The consequential VERBS the spec names route onto the same EXECUTE rung, so
    # each is forced to carry an approval token (proving the verb mapping).
    for verb in ("grade", "send", "publish", "delete", "charge"):
        r = client.post(
            f"/capabilities/coursework/{verb}",
            headers=_auth(token),
            json={"subject_uuid": _TEACHER},
        )
        assert r.status_code == 403, f"{verb} should require approval"
        assert r.json()["reason"] == "approval_required", verb


@pytest.mark.skipif(not workflow_app.available(), reason="workflow runtime not installed")
def test_consequential_execute_with_approval_is_admitted_and_dispatched():
    """With the X-Approval-Token the wall admits the consequential EXECUTE rung
    and it is dispatched into the workflow runtime."""
    token = _dev_token(_TEACHER)
    rec = client.post(
        "/capabilities/intelligence-views/recommend",
        headers=_auth(token),
        json={"effect_verb": "send", "owner_ref": _TEACHER, "consent_ref": _CONSENT},
    ).json()["result"]
    rid = rec["recommendation_id"]

    # Approve first (records the human decision), then execute WITH the token.
    client.post(
        "/capabilities/intelligence-views/actioned",
        headers=_auth(token),
        json={"recommendation_id": rid, "decision": "approve", "decided_by": _DECIDER, "consent_ref": _CONSENT},
    )
    ok = client.post(
        "/capabilities/intelligence-views/execute",
        headers=_auth(token, approval="human-approved-by-teacher"),
        json={"recommendation_id": rid, "capability": "communication.send", "consent_ref": _CONSENT},
    )
    assert ok.status_code == 200, ok.text
    result = ok.json()["result"]
    assert result["dispatched"] is True
    assert result["approval_honored"] is True
    assert result["cleared"] is True


# --------------------------------------------------------------------------- #
# 2. recommend -> approve -> execute emits all four workflow events.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not workflow_app.available(), reason="workflow runtime not installed")
def test_recommend_approve_execute_emits_all_events():
    """The full loop through the door persists recommendation.created,
    recommendation.actioned, approval.given and action.executed to the event
    store. Execute BEFORE approval emits nothing (the ladder holds)."""
    token = _dev_token(_TEACHER)

    # recommend a CONSEQUENTIAL action (send) so the loop reaches action.executed.
    rec = client.post(
        "/capabilities/intelligence-views/recommend",
        headers=_auth(token),
        json={
            "cohort_label": "Class 10-B",
            "topic_label": "Trigonometry",
            "gap_type": "prerequisite",
            "effect_verb": "send",
            "owner_ref": _TEACHER,
            "subject_uuid": _TEACHER,
            "consent_ref": _CONSENT,
        },
    ).json()["result"]
    rid = rec["recommendation_id"]
    assert rec["is_consequential"] is True
    assert rec["ladder_stage"] == "execute_with_permission"
    assert rec["event"]["type"] == "recommendation.created"
    assert rec["event"]["persisted"] is True

    # execute BEFORE approval -> the runtime refuses (no action.executed event).
    before = client.post(
        "/capabilities/intelligence-views/execute",
        headers=_auth(token, approval="present-but-not-yet-approved"),
        json={"recommendation_id": rid, "consent_ref": _CONSENT},
    ).json()["result"]
    assert before["cleared"] is False
    assert before["events"] == []

    # approve -> recommendation.actioned + approval.given.
    approved = client.post(
        "/capabilities/intelligence-views/actioned",
        headers=_auth(token),
        json={"recommendation_id": rid, "decision": "approve", "decided_by": _DECIDER, "consent_ref": _CONSENT},
    ).json()["result"]
    assert [e["type"] for e in approved["events"]] == ["recommendation.actioned", "approval.given"]
    assert all(e["persisted"] for e in approved["events"])

    # execute AFTER approval -> action.executed.
    executed = client.post(
        "/capabilities/intelligence-views/execute",
        headers=_auth(token, approval="human-approved-by-teacher"),
        json={"recommendation_id": rid, "capability": "communication.send", "consent_ref": _CONSENT},
    ).json()["result"]
    assert executed["cleared"] is True
    assert [e["type"] for e in executed["events"]] == ["action.executed"]
    assert executed["events"][0]["persisted"] is True

    # All four loop events were persisted, in loop order.
    emitted = (
        [rec["event"]["type"]]
        + [e["type"] for e in approved["events"]]
        + [e["type"] for e in executed["events"]]
    )
    assert emitted == [
        "recommendation.created",
        "recommendation.actioned",
        "approval.given",
        "action.executed",
    ]


# --------------------------------------------------------------------------- #
# 3. POST /v1/intelligence/read is actually SERVED by the spine.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not intelligence_views.available(), reason="intelligence engine not installed")
def test_intelligence_read_route_is_served_by_the_spine():
    """The /v1/intelligence/read HTTP handler the gateway forwards to is bound
    (no longer glue-pending): it returns the governed view from the ONE engine."""
    # The in-process mount the gateway forwards learning/intelligence-views.read to.
    resp = client.post(
        "/internal/intelligence/v1/intelligence/read",
        json={"view": "mastery:" + _TOPIC, "subject_uuid": _STUDENT_A},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The contract shape (engine-computed), not a stub.
    assert "reading" in body and "plainLanguage" in body
    assert body["reading"]["band"] in (
        "not-started", "emerging", "developing", "secure", "independent",
    )

    # The recommendations view is an array (the web's fallback contract).
    recs = client.post(
        "/internal/intelligence/v1/intelligence/read",
        json={"view": "recommendations"},
    )
    assert recs.status_code == 200
    assert isinstance(recs.json(), list)

    # An unknown view is a clean 422 (not a crash, not a stub).
    bad = client.post("/internal/intelligence/v1/intelligence/read", json={"view": "nope"})
    assert bad.status_code == 422


def test_intelligence_read_route_health_reports_engine():
    resp = client.get("/internal/intelligence/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "intelligence-read"
