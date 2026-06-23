"""Phone-OTP-first remains the primary path and writes access history."""

from __future__ import annotations

from .conftest import STUDENT


def test_otp_start_then_verify_issues_token(client):
    r = client.post("/v1/identity/auth/otp/start", json={"phone": "+10000000001", "app": "school"})
    assert r.status_code == 202
    challenge_id = r.json()["challenge_id"]

    r2 = client.post("/v1/identity/auth/otp/verify", json={"challenge_id": challenge_id, "code": "123456"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    canonical = body["canonical_uuid"]

    # No PII leaks anywhere in the token response.
    assert "+10000000001" not in r2.text

    # Verifying writes a full access-history entry.
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    h = client.get("/v1/identity/access-history", params={"canonical_uuid": canonical}, headers=headers)
    assert h.status_code == 200
    actions = [e["action"] for e in h.json()]
    assert "auth.otp.verified" in actions


def test_otp_verify_rejects_unknown_challenge(client):
    import uuid
    r = client.post("/v1/identity/auth/otp/verify",
                    json={"challenge_id": str(uuid.uuid4()), "code": "1"})
    assert r.status_code == 401
