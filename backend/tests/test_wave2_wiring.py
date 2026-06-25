"""Wave-2 backend wiring — the gaps closed end to end, fully offline.

Proves, through the deployable's governed capability door (Starlette TestClient,
no network / DB / secret):

  GAP#10  Each newly-routed feature-module front (institution, scheduling,
          attendance, communication translate/make_tasks/ptm, teacher-growth) is
          ADMITTED by the wall and DISPATCHED to the existing module logic — the
          circuit identity -> gateway -> capability -> (event).

  GAP#2   recommend -> approve -> execute on ONE engine-derived recommendation id
          resolves the SAME object end to end (no 404 unknown_recommendation) and
          emits all three loop events INCLUDING action.executed — even when the
          process recommendation mirror is cleared between the rungs (durability).

  GAP#3/#5/#7  A governance AI-control toggle PERSISTS the new state and emits an
          immutable audit entry the audit-trail READ returns; the consequential
          toggle is approval-gated at the wall (it can never auto-fire).

  GAP#8   translate returns reader-language text (content preserved, never
          dropped) via the existing translation interface.

CONFIDENTIALITY: every id is an opaque canonical ref. No PII, no names, no board,
no real pricing.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from backend import dispatch, intelligence_views, workflow_app
from backend.main import app

client = TestClient(app)

_TEACHER = "11111111-1111-4111-8111-111111111111"
_ADMIN = "33333333-3333-4333-8333-333333333333"
_DECIDER = "22222222-2222-4222-8222-222222222222"
_CONSENT = "cccccccc-0000-4000-8000-000000000003"


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


def _result(resp) -> dict:
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "admitted"
    return body["result"]


# --------------------------------------------------------------------------- #
# GAP#10 — each newly-routed capability admits + dispatches.
# --------------------------------------------------------------------------- #
def test_communication_translate_admits_and_returns_reader_language_text():
    """GAP#8 — the translate front is routed; reusing the translation interface it
    renders for the reader and NEVER drops content (passthrough degrade keeps the
    text intact). A READ; admitted on a verified token."""
    token = _dev_token(_TEACHER)
    text = "The mitochondria is the powerhouse of the cell."
    resp = client.post(
        "/capabilities/communication/translate",
        headers=_auth(token),
        json={"subject_uuid": _TEACHER, "text": text, "preferred_lang": "hi"},
    )
    result = _result(resp)
    assert result["dispatched"] is True
    assert result["operation"] == "translate"
    # Reader-language text: content preserved (intact on the degraded passthrough),
    # target language honoured, never dropped.
    assert result["rendered_text"]  # non-empty
    assert text in result["rendered_text"]  # content never dropped
    assert result["target_lang"] == "hi"
    assert result["status"] in ("translated", "passthrough")


def test_communication_make_tasks_admits_and_dispatches_conversation_to_task():
    """GAP#9 — conversation-to-task: a screened message is promoted into an owned,
    tracked task and a communication.task_created event is emitted."""
    token = _dev_token(_TEACHER)
    resp = client.post(
        "/capabilities/communication/make_tasks",
        headers=_auth(token),
        json={
            "subject_uuid": _TEACHER,
            "body": "Could we follow up on the homework plan?",
            "title": "Homework follow-up",
            "owner_ref": _TEACHER,
            "why": "Routed from a parent message.",
            "consent_ref": _CONSENT,
        },
    )
    result = _result(resp)
    assert result["dispatched"] is True
    assert result["task_id"]
    assert result["event"]["type"] == "communication.task_created"


def test_communication_ptm_admits_and_prepares_a_booking():
    """GAP#12 — PTM: a booking is PROPOSED (awaiting human confirm) and the
    parent's screened prep is built; a ptm.requested event is emitted."""
    token = _dev_token(_TEACHER)
    resp = client.post(
        "/capabilities/communication/ptm",
        headers=_auth(token),
        json={
            "subject_uuid": _TEACHER,
            "parent_ref": "p0000000-0000-4000-8000-00000000000p",
            "teacher_ref": _TEACHER,
            "child_context_ref": "child-1",
            "consent_ref": _CONSENT,
        },
    )
    result = _result(resp)
    assert result["dispatched"] is True
    assert result["booking_id"]
    # PROPOSED, never auto-confirmed (the permission ladder).
    assert result["is_confirmed"] is False
    assert result["event"]["type"] == "ptm.requested"


def test_institution_policy_admits_and_reads_config():
    token = _dev_token(_TEACHER)
    result = _result(client.post(
        "/capabilities/institution/policy",
        headers=_auth(token),
        json={"subject_uuid": _TEACHER},
    ))
    assert result["dispatched"] is True
    assert result["service_name"] == "institution"


def test_scheduling_recommend_recovery_admits_and_dispatches():
    token = _dev_token(_TEACHER)
    result = _result(client.post(
        "/capabilities/scheduling/recommend_recovery",
        headers=_auth(token),
        json={"subject_uuid": _TEACHER, "expected_periods": 40.0, "delivered_periods": 25},
    ))
    assert result["dispatched"] is True
    # Behind schedule -> drifting; the recovery menu is the engine's, never auto-applied.
    assert result["is_drifting"] is True


def test_attendance_capture_admits_and_summarises_a_proposal():
    token = _dev_token(_TEACHER)
    result = _result(client.post(
        "/capabilities/attendance/capture",
        headers=_auth(token),
        json={
            "subject_uuid": _TEACHER,
            "session_id": "session-1",
            "roster_refs": ["a", "b", "c"],
            "absent_refs": ["b"],
        },
    ))
    assert result["dispatched"] is True
    # A PROPOSAL — never final until a human confirms (the permission ladder).
    assert result["is_final"] is False
    assert result["summary"]["present"] == 2
    assert result["summary"]["absent"] == 1


def test_teacher_growth_coaching_admits_and_dispatches_non_punitive_summary():
    token = _dev_token(_TEACHER)
    result = _result(client.post(
        "/capabilities/teacher-growth/coaching",
        headers=_auth(token),
        json={
            "subject_uuid": _TEACHER,
            "teacher_ref": _TEACHER,
            "total_questions": 10,
            "higher_order_questions": 2,
            "lower_order_questions": 8,
        },
    ))
    assert result["dispatched"] is True
    # Teacher-first, never a rating: a plain-language framing, strengths + growth.
    assert isinstance(result["strengths"], list)
    assert isinstance(result["growth_areas"], list)
    assert "rating" not in result["framing"].lower() or "never a rating" in result["framing"].lower()


# --------------------------------------------------------------------------- #
# GAP#2 — recommend -> approve -> execute on ONE engine-derived id, durable.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not (workflow_app.available() and intelligence_views.available()),
    reason="workflow runtime or intelligence engine not installed",
)
def test_engine_derived_recommendation_survives_recommend_approve_execute():
    """The recommendation id is ENGINE-DERIVED (stable) and the SAME object is
    referenced end to end. Even after the process recommendation mirror is CLEARED
    between rungs (simulating a cross-request / restart), approve + execute resolve
    it (no 404 unknown_recommendation) and emit all three events incl.
    action.executed."""
    token = _dev_token(_TEACHER)

    # The engine-derived feed carries stable ids (intelligence_views, not a mock).
    feed = intelligence_views.recommendations()
    assert feed, "engine produced no recommendations to act on"
    rid = feed[0]["recommendation_id"]

    # recommend FROM the engine id -> recommendation.created on the stable id, as a
    # consequential action (send) so the loop can reach action.executed.
    rec = _result(client.post(
        "/capabilities/intelligence-views/recommend",
        headers=_auth(token),
        json={"recommendation_id": rid, "effect_verb": "send",
              "owner_ref": _TEACHER, "consent_ref": _CONSENT},
    ))
    assert rec["recommendation_id"] == rid  # the SAME engine-derived id
    assert rec["event"]["type"] == "recommendation.created"

    # DURABILITY: clear the process mirror — the id must still resolve.
    workflow_app._RECS.clear()

    # approve the SAME id (rehydrated from the engine) -> actioned + approval.given.
    approved = _result(client.post(
        "/capabilities/intelligence-views/actioned",
        headers=_auth(token),
        json={"recommendation_id": rid, "decision": "approve",
              "decided_by": _DECIDER, "effect_verb": "send", "consent_ref": _CONSENT},
    ))
    assert [e["type"] for e in approved["events"]] == ["recommendation.actioned", "approval.given"]

    # Clear again before execute — still resolves the SAME object (durable).
    workflow_app._RECS.clear()

    # execute the SAME id WITH the approval token -> action.executed (the REAL
    # outcome of clearing the gate, not an echoed decision string).
    executed = _result(client.post(
        "/capabilities/intelligence-views/execute",
        headers=_auth(token, approval="human-approved-by-teacher"),
        json={"recommendation_id": rid, "capability": "communication.send",
              "effect_verb": "send", "consent_ref": _CONSENT},
    ))
    assert executed["cleared"] is True
    assert [e["type"] for e in executed["events"]] == ["action.executed"]

    # The three rungs referenced ONE engine-derived id and emitted all three events.
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


def test_engine_derived_ids_are_stable_across_calls():
    """Same gap on the same topic -> same recommendation id (the durability
    keystone). If the engine is absent the feed is simply empty."""
    a = intelligence_views.recommendations()
    b = intelligence_views.recommendations()
    assert [r["recommendation_id"] for r in a] == [r["recommendation_id"] for r in b]


# --------------------------------------------------------------------------- #
# GAP#3/#5/#7 — a governance toggle persists + emits an immutable audit entry.
# --------------------------------------------------------------------------- #
def test_governance_toggle_requires_approval_at_the_wall():
    """The AI-control toggle rides the EXECUTE rung (consequential) so the wall
    forces an X-Approval-Token; without one it is DENIED and can never auto-fire."""
    token = _dev_token(_ADMIN, role="admin")
    denied = client.post(
        "/capabilities/governance/toggle",
        headers=_auth(token),
        json={"subject_uuid": _ADMIN, "capability": "vidya.companion",
              "enabled": False, "reason": "incident"},
    )
    assert denied.status_code == 403
    assert denied.json()["reason"] == "approval_required"


@pytest.mark.skipif(
    not __import__("backend.governance_app", fromlist=["available"]).available(),
    reason="governance runtime not installed",
)
def test_governance_toggle_persists_and_audits_then_audit_trail_reads_it():
    """With the approval token the toggle is admitted; it PERSISTS the new state,
    records an immutable privileged audit entry, AND emits a governance.toggled
    event to the event store. The audit-trail READ then returns the entry."""
    token = _dev_token(_ADMIN, role="admin")
    cap = "vidya.companion.test"

    toggled = _result(client.post(
        "/capabilities/governance/toggle",
        headers=_auth(token, approval="human-approved-by-admin"),
        json={"subject_uuid": _ADMIN, "actor_uuid": _ADMIN, "capability": cap,
              "enabled": False, "reason": "safety incident", "consent_ref": _CONSENT},
    ))
    assert toggled["dispatched"] is True
    assert toggled["enabled"] is False
    assert toggled["audited"] is True
    # The action is also a clean attributed event in the immutable event store.
    assert toggled["event"]["type"] == "governance.toggled"

    # The audit-trail READ surfaces the immutable privileged entry.
    trail = _result(client.post(
        "/capabilities/governance/audit_trail",
        headers={**_auth(token), "X-Consent-Purpose": "governance"},
        json={"subject_uuid": _ADMIN, "resource": cap},
    ))
    assert trail["count"] >= 1
    actions = [r["action"] for r in trail["records"]]
    assert "control_centre.emergency_disable" in actions
    assert all(r["privileged"] for r in trail["records"])


@pytest.mark.skipif(
    not __import__("backend.governance_app", fromlist=["available"]).available(),
    reason="governance runtime not installed",
)
def test_governance_breakglass_requires_a_reason():
    """Break-glass is refused without a reason (privileged access law)."""
    from backend import governance_app

    status, body = governance_app.do_breakglass(
        {"capability": "pii.read", "reason": "  ", "actor_uuid": _ADMIN}
    )
    assert status == 422
    assert body["error"] == "breakglass_refused"
