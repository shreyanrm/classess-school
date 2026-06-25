"""Smoke proving the single deployable is FULLY FUNCTIONAL (offline, no network).

Asserts the three fixes hold together:

  (a) EVERY capability in ``loader.CAPABILITY_MODULES`` loads (none skipped),
      including the FLAT packages (content, learning) that have no ``app/``.
  (b) ``GET /health`` lists every capability behind the wall.
  (c) A clearly-marked DEV-UNSIGNED token carrying a valid uuid + a teacher
      membership PASSES the wall's token verifier (the deny reason is never
      ``invalid_token``/``no_token``) for a learning READ door. RBAC/ABAC may
      still allow or deny downstream — but the TOKEN must verify.

Runs fully offline with a Starlette ``TestClient``: no network, no DB, no secret.
"""

from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from backend import loader
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


def test_every_capability_module_loads_none_skipped():
    for name in loader.CAPABILITY_MODULES:
        mod = loader.load_capability_module(name)
        assert mod is not None, f"capability module not loaded (skipped): {name}"


def test_health_lists_all_capabilities():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["wall"] == "active"
    caps = set(body["capabilities"])
    # Every routable capability module must appear behind the wall.
    for name in (
        "institution",
        "scheduling",
        "coursework",
        "learning",
        "content",
        "learner-record",
        "communication",
        "attendance",
        "planning",
        "classroom",
    ):
        assert name in caps, f"capability missing from /health: {name}"


def test_dev_unsigned_teacher_token_passes_the_wall_verifier():
    # A valid uuid + teacher membership. With no public key / introspect url
    # configured (the deploy case), the wall MUST accept this dev-unsigned token.
    token = _dev_token("11111111-1111-4111-8111-111111111111", "teacher")
    resp = client.post(
        "/capabilities/learning/read",
        headers={"Authorization": f"Bearer {token}"},
        json={"subject_uuid": "11111111-1111-4111-8111-111111111111"},
    )
    # The TOKEN must verify: the wall must NOT reject it as no_token/invalid_token.
    # (RBAC/ABAC/consent may still allow or deny — that is the wall's job.)
    if resp.status_code == 200:
        assert resp.json()["status"] == "admitted"
    else:
        reason = resp.json().get("reason")
        assert reason not in ("no_token", "invalid_token"), (
            f"dev-unsigned teacher token failed the TOKEN gate: {reason}"
        )


def test_garbage_token_is_still_rejected():
    # Deny-by-default still holds: a non-dev, unverifiable token is invalid.
    resp = client.post(
        "/capabilities/learning/read",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"subject_uuid": "abc"},
    )
    assert resp.status_code in (401, 403)
    assert resp.json()["reason"] in ("no_token", "invalid_token")
