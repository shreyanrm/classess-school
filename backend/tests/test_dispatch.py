"""SpineLive 2 — the wall door DISPATCHES to the capability operation.

Proves the door no longer stops at ``admitted`` for the loop capabilities: a
DEV-UNSIGNED token that passes the wall now reaches the real engine surface and
the response carries a ``result`` with ``dispatched: true``. Deny-by-default
still holds: an unauthenticated call is denied at the wall, before any dispatch.

Runs fully offline (Starlette ``TestClient``): no network, no DB, no secret.
"""

from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _dev_token(canonical_uuid: str, role: str, scope: str = "inst-1") -> str:
    claims = {
        "canonical_uuid": canonical_uuid,
        "app": "school",
        "memberships": [{"app": "school", "role": role, "scope": scope}],
    }
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "DEV-UNSIGNED." + body


_TEACHER = "11111111-1111-4111-8111-111111111111"


def test_admitted_op_is_dispatched_to_the_engine():
    """A teacher recording a practice attempt passes the wall AND reaches the
    learning engine: the response carries a dispatched result from the real
    ``grade_topic_quiz`` surface (comprehension-weighted), not a bare admit."""
    token = _dev_token(_TEACHER, "teacher")
    resp = client.post(
        "/capabilities/learning/record_practice",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subject_uuid": _TEACHER,
            "topic_id": "fractions",
            "items": [
                {"correct": True, "independent": True, "difficulty": 0.8},
                {"correct": False, "independent": False, "difficulty": 0.4},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "admitted"
    result = body["result"]
    assert result["dispatched"] is True
    assert result["operation"] == "record_practice"
    assert result["topic_id"] == "fractions"
    # The engine actually graded it (real comprehension score in [0, 1]).
    assert 0.0 <= result["comprehension_score"] <= 1.0
    assert isinstance(result["passed"], bool)


def test_evaluate_submission_records_emits_evidence_and_holds_the_ladder():
    """The LoopModules circuit: a teacher posting a submission for grading passes
    the wall, the engine evaluates it (banded), and the evidence the intelligence
    engine consumes is emitted (attempt.recorded + submission.created +
    score.recorded). Grading is consequential -> the mark is NEVER final and,
    with no approval token, is awaiting human approval (the permission ladder)."""
    token = _dev_token(_TEACHER, "teacher")
    resp = client.post(
        "/capabilities/coursework/evaluate_submission",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subject_uuid": _TEACHER,
            "submission_ref": "22222222-2222-4222-8222-222222222222",
            "consequential": True,
            "responses": [
                {
                    "question_ref": "33333333-3333-4333-8333-333333333333",
                    "expression": "3*4",
                    "learner_answer": 12.0,
                    "independent": True,
                    "difficulty": 0.5,
                    "time_taken_ms": 20000,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["dispatched"] is True
    assert result["operation"] == "evaluate_submission"
    # Banded result is surfaced.
    assert result["confidence_band"] in ("low", "medium", "high")
    # Permission ladder: a consequential grade is never auto-final, and with no
    # approval token presented it is awaiting human approval.
    assert result["consequential"] is True
    assert result["final"] is False
    assert result["awaiting_approval"] is True
    assert result["approval_honored"] is False
    # The evidence the engine consumes was emitted (one attempt + submission +
    # score), and degrades cleanly (no store wired -> not persisted).
    types = [e["type"] for e in result["events_emitted"]]
    assert "attempt.recorded" in types
    assert "submission.created" in types
    assert "score.recorded" in types


def test_evaluate_submission_with_approval_honors_the_ladder():
    """Presenting a human approval token clears the awaiting-approval rung; the
    engine still refuses to auto-finalise a consequential mark on its own."""
    token = _dev_token(_TEACHER, "teacher")
    resp = client.post(
        "/capabilities/coursework/evaluate_submission",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Approval-Token": "human-approved-by-marker",
        },
        json={
            "subject_uuid": _TEACHER,
            "submission_ref": "22222222-2222-4222-8222-222222222222",
            "consequential": True,
            "responses": [
                {"question_ref": "33333333-3333-4333-8333-333333333333", "expression": "2+2", "learner_answer": 4.0}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["approval_honored"] is True
    assert result["awaiting_approval"] is False
    assert result["final"] is False  # engine never finalises alone


def test_denied_op_never_dispatches():
    """Deny-by-default: an unauthenticated dispatch attempt is denied at the
    wall — no ``result`` is ever returned (the engine is never reached)."""
    resp = client.post(
        "/capabilities/learning/record_practice",
        json={"subject_uuid": _TEACHER, "topic_id": "fractions", "items": []},
    )
    assert resp.status_code in (401, 403)
    body = resp.json()
    assert body["error"] == "denied"
    assert body["reason"] in ("no_token", "invalid_token")
    assert "result" not in body
