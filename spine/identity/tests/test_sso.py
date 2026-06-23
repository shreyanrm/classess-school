"""SSO single-front-door: start/callback for Google/Apple/Microsoft/SAML,
auto-provision one canonical identity on first signup, degrade cleanly."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("provider", ["google", "apple", "microsoft", "saml"])
def test_sso_start_degraded_returns_state_and_url(client, provider, monkeypatch):
    for name in ("CLSS_IDENTITY_DEV_GOOGLE_CLIENT_ID", "CLSS_IDENTITY_DEV_APPLE_CLIENT_ID",
                 "CLSS_IDENTITY_DEV_MICROSOFT_CLIENT_ID", "CLSS_IDENTITY_DEV_SAML_ENTITY_ID",
                 "CLSS_IDENTITY_DEV_SAML_SSO_URL"):
        monkeypatch.delenv(name, raising=False)
    r = client.post("/v1/identity/auth/sso/start", json={"provider": provider, "app": "school"})
    assert r.status_code == 202
    body = r.json()
    assert body["provider"] == provider
    assert body["degraded"] is True
    assert body["state"]
    assert body["authorization_url"]


def test_sso_start_configured_builds_provider_url(client, monkeypatch):
    monkeypatch.setenv("CLSS_IDENTITY_DEV_GOOGLE_CLIENT_ID", "client-123")
    r = client.post("/v1/identity/auth/sso/start", json={"provider": "google", "app": "school"})
    body = r.json()
    assert body["degraded"] is False
    assert "accounts.google.com" in body["authorization_url"]
    assert "client-123" in body["authorization_url"]


def test_sso_callback_auto_provisions_one_identity(client):
    start = client.post("/v1/identity/auth/sso/start", json={"provider": "google", "app": "school"}).json()
    cb = client.post("/v1/identity/auth/sso/callback", json={
        "provider": "google", "state": start["state"], "subject": "google-sub-1",
        "email": "user@example.test", "full_name": "A Person",
    })
    assert cb.status_code == 200
    canonical_a = cb.json()["canonical_uuid"]
    # No provider PII in the response.
    assert "user@example.test" not in cb.text
    assert "A Person" not in cb.text

    # Same subject signing in again resolves to the SAME canonical identity.
    start2 = client.post("/v1/identity/auth/sso/start", json={"provider": "google", "app": "school"}).json()
    cb2 = client.post("/v1/identity/auth/sso/callback", json={
        "provider": "google", "state": start2["state"], "subject": "google-sub-1",
    })
    assert cb2.json()["canonical_uuid"] == canonical_a


def test_sso_callback_rejects_unknown_state(client):
    r = client.post("/v1/identity/auth/sso/callback",
                    json={"provider": "google", "state": "forged", "subject": "x"})
    assert r.status_code == 401


def test_sso_callback_state_is_provider_bound(client):
    start = client.post("/v1/identity/auth/sso/start", json={"provider": "google", "app": "school"}).json()
    r = client.post("/v1/identity/auth/sso/callback",
                    json={"provider": "apple", "state": start["state"], "subject": "x"})
    assert r.status_code == 401


def test_sso_callback_requires_a_subject(client):
    start = client.post("/v1/identity/auth/sso/start", json={"provider": "google", "app": "school"}).json()
    r = client.post("/v1/identity/auth/sso/callback",
                    json={"provider": "google", "state": start["state"]})
    assert r.status_code == 401
