"""Offline smoke tests for the single deployable.

Two invariants this deployable must hold from line one:

  1. ``GET /health`` is 200 (the process is alive and the wall is wired).
  2. An UNAUTHENTICATED capability call is DENIED by the gateway wall
     (deny-by-default) — no module is reachable without passing the wall.

These run fully offline with a Starlette ``TestClient`` (no network, no DB, no
secret). They import nothing that performs I/O at import time.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_is_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["wall"] == "active"
    # The capability modules are declared as routable capabilities behind the wall.
    assert "institution" in body["capabilities"]


def test_unauthenticated_capability_is_denied():
    # No Authorization header -> the wall denies (deny-by-default).
    resp = client.post("/capabilities/institution/read", json={"subject_uuid": "abc"})
    assert resp.status_code in (401, 403)
    body = resp.json()
    assert body["error"] == "denied"
    # With no token the wall fails closed at the auth gate.
    assert body["reason"] in ("no_token", "invalid_token")


def test_invalid_token_capability_is_denied():
    # A bearer token present but unverifiable -> denied (no real verifier wired,
    # so the wall's safe-default verifier rejects every token).
    resp = client.post(
        "/capabilities/institution/read",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"subject_uuid": "abc"},
    )
    assert resp.status_code in (401, 403)
    assert resp.json()["error"] == "denied"


def test_unknown_capability_operation_is_404():
    resp = client.post("/capabilities/institution/teleport", json={})
    assert resp.status_code == 404
