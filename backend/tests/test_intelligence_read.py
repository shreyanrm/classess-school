"""The SPINE intelligence read — governed views from the ONE engine + fallback.

Asserts the SpineLive 1 contract end to end, fully offline (TestClient, no
network, no DB, no secret):

  SPINE ANSWERS WHEN CONFIGURED
    A governed read through the wall (POST /capabilities/{learning|intelligence-
    views}/read with a `view` selector + the consent scope) returns the spine's
    governed view — mastery / gaps / recommendations / class-insights — computed
    by REPLAYING the event store through the ONE Python engine. The body matches
    the contract shape the web surface's gateway-first read trusts (so it does
    NOT fall back).

  FALLBACK ON 503 / DENY
    When the ONE engine is unavailable the read returns 503 (degraded) so the
    surface falls back to its in-browser engine port. And a cross-context read
    WITHOUT the consent scope is DENIED (403) — also a fallback trigger — proving
    the wall still gates the spine faucet (firehose-up / faucet-down, INVARIANT).

CONFIDENTIALITY: every id is an opaque canonical ref (generic Student A/B). No
PII, no names, no board, no real pricing.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from backend import intelligence_views
from backend.main import app

client = TestClient(app)

# Opaque refs the seed scenario uses (the web's ROSTER shares the Student tokens).
_STUDENT_A = "a0000000-0000-4000-8000-00000000000a"
_TOPIC = "70000000-0000-4000-8000-000000000001"


def _dev_token(canonical_uuid: str, role: str, consent_scopes: list[str]) -> str:
    """A clearly-marked DEV-UNSIGNED token carrying opaque claims + the consent
    scopes the cross-context read needs. No secret; the wall accepts it only in
    dev (no public key / introspect configured)."""
    claims = {
        "canonical_uuid": canonical_uuid,
        "app": "school",
        "memberships": [{"app": "school", "role": role, "scope": "inst-1"}],
        "consent_scopes": consent_scopes,
    }
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "DEV-UNSIGNED." + body


def _read(capability: str, token: str, purpose: str, payload: dict):
    return client.post(
        f"/capabilities/{capability}/read",
        headers={"Authorization": f"Bearer {token}", "X-Consent-Purpose": purpose},
        json=payload,
    )


# --------------------------------------------------------------------------- #
# SPINE ANSWERS WHEN CONFIGURED
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not intelligence_views.available(), reason="intelligence engine not installed")
def test_spine_answers_mastery_when_configured():
    token = _dev_token(_STUDENT_A, "learner", ["learning.read"])
    resp = _read("learning", token, "intelligence.mastery", {"subject_uuid": _STUDENT_A, "view": f"mastery:{_TOPIC}"})
    assert resp.status_code == 200
    body = resp.json()
    # The contract shape the web's isMasteryShape guard trusts (so it does NOT
    # fall back): a structured reading + plain-language, computed by the engine.
    assert "reading" in body and "plainLanguage" in body
    assert body["reading"]["band"] in ("not-started", "emerging", "developing", "secure", "independent")
    # Replayed from events, not the generic admitted ack.
    assert body.get("status") != "admitted"


@pytest.mark.skipif(not intelligence_views.available(), reason="intelligence engine not installed")
def test_spine_answers_gaps_when_configured():
    token = _dev_token(_STUDENT_A, "learner", ["learning.read"])
    resp = _read("learning", token, "intelligence.gaps", {"subject_uuid": _STUDENT_A, "view": f"gaps:{_TOPIC}"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)  # the web's gap fallback expects an array


@pytest.mark.skipif(not intelligence_views.available(), reason="intelligence engine not installed")
def test_spine_answers_recommendations_when_configured():
    token = _dev_token(_STUDENT_A, "teacher", ["intelligence-views.read"])
    resp = _read("intelligence-views", token, "intelligence.recommendations", {"subject_uuid": _STUDENT_A, "view": "recommendations"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)  # the web's recommendations fallback expects an array


@pytest.mark.skipif(not intelligence_views.available(), reason="intelligence engine not installed")
def test_spine_answers_class_insights_when_configured():
    token = _dev_token(_STUDENT_A, "teacher", ["intelligence-views.read"])
    resp = _read("intelligence-views", token, "intelligence.class-insights", {"subject_uuid": "inst-1", "view": "class-insights"})
    assert resp.status_code == 200
    body = resp.json()
    # The contract shape the web's isClassInsightsShape guard trusts.
    assert "summary" in body and "reads" in body and isinstance(body["reads"], list)


# --------------------------------------------------------------------------- #
# FALLBACK ON 503 / DENY — the surface degrades to its in-browser engine port.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not intelligence_views.available(), reason="intelligence engine not installed")
def test_engine_unavailable_returns_503_so_surface_falls_back(monkeypatch):
    # Simulate the ONE engine being unavailable on this deploy (e.g. a dependency
    # absent). The read must return 503 (degraded), NOT a non-contract body, so
    # the web falls back to lib/engine cleanly.
    monkeypatch.setattr(intelligence_views, "available", lambda: False)
    token = _dev_token(_STUDENT_A, "learner", ["learning.read"])
    resp = _read("learning", token, "intelligence.mastery", {"subject_uuid": _STUDENT_A, "view": f"mastery:{_TOPIC}"})
    assert resp.status_code == 503
    assert resp.json().get("status") == "degraded"


def test_cross_context_read_without_consent_is_denied():
    # The wall still gates the spine faucet: a cross-context read with NO consent
    # scope is denied (403) — a fallback trigger for the surface (deny -> engine).
    token = _dev_token(_STUDENT_A, "learner", [])  # no consent scope granted
    resp = _read("learning", token, "intelligence.mastery", {"subject_uuid": _STUDENT_A, "view": f"mastery:{_TOPIC}"})
    assert resp.status_code == 403
    assert resp.json().get("reason") == "consent_required"
