"""The generate-and-verify GENERATORS reachable end to end through the governed
capability door: identity -> gateway(wall) -> capability -> verified artifact.

Proves, fully offline (Starlette TestClient, no network / DB / provider key):

  * each generator ADMITS for a teacher and DISPATCHES to the engine that
    already exists in modules/content + modules/planning (generate-and-verify);
  * an unauthorized role (student) is DENIED at the wall (deny-by-default);
  * the result is a VERIFIED artifact behind the confidence gate — with NO
    Track-1 provider key wired, it is withheld with an OBSERVABLE marker
    (served=False + a non-empty review reason), never a silent fabrication;
  * each PREPARES a draft (the PREPARE rung) — it never auto-publishes/assigns.

CONFIDENTIALITY: every id is an opaque canonical ref. No PII / names / board.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

_TEACHER = "11111111-1111-4111-8111-111111111111"
_STUDENT = "55555555-5555-4555-8555-555555555555"


def _dev_token(canonical_uuid: str, role: str = "teacher") -> str:
    claims = {
        "canonical_uuid": canonical_uuid,
        "app": "school",
        "memberships": [{"app": "school", "role": role, "scope": "inst-1"}],
    }
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "DEV-UNSIGNED." + body


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _result(resp) -> dict:
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "admitted"
    return body["result"]


def _assert_verified_artifact(result: dict) -> None:
    """A served artifact passed the confidence gate; an unserved one carries an
    OBSERVABLE degrade marker (a non-empty review reason / withheld set), never a
    silent mock. Either way the engine ran (dispatched) — no fabrication."""
    assert result["dispatched"] is True
    if result.get("served"):
        return  # gate passed — a verified artifact was served
    marker = result.get("review_reason") or result.get("withheld")
    assert marker, "an unserved artifact must show an OBSERVABLE degrade marker"


# (capability, operation, minimal body) — each PREPARES a verified draft.
_CASES = [
    (
        "content",
        "generate_worksheet",
        {"topic_id": "t1", "items": [{"kind": "practice_item", "content_payload": {"prompt": "2+2", "answer": "4"}}]},
    ),
    (
        "planning",
        "generate_course_outline",
        {"subject_uuid": _TEACHER, "outline_payload": {}, "claimed_outcome_ids": ["o1"], "known_outcome_ids": ["o1"]},
    ),
    ("planning", "generate_lesson_plan", {"topic_id": "t1", "lesson_payload": {}}),
    ("planning", "generate_session_plan", {"lesson_plan": {}, "timetable_slot": {}}),
]


@pytest.mark.parametrize("capability,operation,extra", _CASES)
def test_generator_admits_for_teacher_and_returns_verified_artifact(capability, operation, extra):
    token = _dev_token(_TEACHER)
    body = {"subject_uuid": _TEACHER, **extra}
    result = _result(client.post(f"/capabilities/{capability}/{operation}", headers=_auth(token), json=body))
    assert result["operation"] == operation
    _assert_verified_artifact(result)
    # PREPARE rung: a draft, not a consequential publish/assign. No approval was
    # needed to PREPARE it (the generation never auto-published).
    assert result.get("approval_honored") in (False, None)


@pytest.mark.parametrize("capability,operation,extra", _CASES)
def test_generator_denies_unauthorized_role(capability, operation, extra):
    """A student is not staff — the wall denies the generator write
    (deny-by-default; RBAC). It never reaches the engine."""
    token = _dev_token(_STUDENT, role="student")
    body = {"subject_uuid": _STUDENT, **extra}
    resp = client.post(f"/capabilities/{capability}/{operation}", headers=_auth(token), json=body)
    assert resp.status_code == 403, resp.text
    assert resp.json()["reason"] == "rbac_denied"


def test_unauthenticated_generator_call_denied():
    """No token -> denied at the wall (401), never inside the module."""
    resp = client.post(
        "/capabilities/planning/generate_lesson_plan",
        json={"subject_uuid": _TEACHER, "topic_id": "t1", "lesson_payload": {}},
    )
    assert resp.status_code == 401, resp.text
