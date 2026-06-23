"""Device register/list/revoke and session risk signals."""

from __future__ import annotations

import uuid

from .conftest import STUDENT


def test_register_list_revoke_device(client, bearer):
    reg = client.post("/v1/identity/devices/register", headers=bearer, json={
        "canonical_uuid": str(STUDENT), "device_fingerprint": "fp-abc",
        "label": "classroom tablet", "platform": "android",
    })
    assert reg.status_code == 201
    device = reg.json()
    device_id = device["device_id"]
    # The opaque fingerprint is vaulted, never returned.
    assert "fp-abc" not in reg.text
    assert device["label"] == "classroom tablet"
    assert device["revoked_at"] is None

    lst = client.get("/v1/identity/devices", headers=bearer, params={"canonical_uuid": str(STUDENT)})
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    rev = client.post(f"/v1/identity/devices/{device_id}/revoke", headers=bearer,
                      params={"canonical_uuid": str(STUDENT)})
    assert rev.status_code == 204

    lst2 = client.get("/v1/identity/devices", headers=bearer, params={"canonical_uuid": str(STUDENT)})
    assert lst2.json()[0]["revoked_at"] is not None


def test_revoke_unknown_device_404(client, bearer):
    r = client.post(f"/v1/identity/devices/{uuid.uuid4()}/revoke", headers=bearer,
                    params={"canonical_uuid": str(STUDENT)})
    assert r.status_code == 404


def test_session_risk_low_medium_high(client, bearer):
    sid = str(uuid.uuid4())
    low = client.post("/v1/identity/sessions/risk", headers=bearer, json={
        "canonical_uuid": str(STUDENT), "session_id": sid, "signals": [],
    })
    assert low.json()["risk"] == "low"
    assert low.json()["requires_step_up"] is False

    med = client.post("/v1/identity/sessions/risk", headers=bearer, json={
        "canonical_uuid": str(STUDENT), "session_id": str(uuid.uuid4()), "signals": ["new_device"],
    })
    assert med.json()["risk"] == "medium"

    high = client.post("/v1/identity/sessions/risk", headers=bearer, json={
        "canonical_uuid": str(STUDENT), "session_id": str(uuid.uuid4()),
        "signals": ["impossible_travel"],
    })
    body = high.json()
    assert body["risk"] == "high"
    # PERMISSION LADDER: high RECOMMENDS step-up; identity never blocks alone.
    assert body["requires_step_up"] is True


def test_device_actions_require_bearer(client):
    r = client.get("/v1/identity/devices", params={"canonical_uuid": str(STUDENT)})
    assert r.status_code == 401
