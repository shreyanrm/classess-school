"""The service must import and boot fully offline: no signing key, no asyncpg,
no live network. Degradation is clearly labelled, never a crash."""

from __future__ import annotations

from app import main as main_mod
from app import sso
from app.config import IdentitySettings
from app.store import InMemoryIdentityStore, build_store
from app.tokens import TokenService


def test_app_imports_and_has_routes():
    paths = {r.path for r in main_mod.app.routes}
    assert "/v1/identity/auth/sso/start" in paths
    assert "/v1/identity/auth/sso/callback" in paths
    assert "/v1/identity/devices/register" in paths
    assert "/v1/identity/access-history" in paths
    assert "/v1/identity/access-grants" in paths


def test_store_degrades_to_in_memory_without_db():
    assert isinstance(build_store(None), InMemoryIdentityStore)


def test_settings_report_missing_config_by_name_only():
    missing = IdentitySettings().degraded_reasons()
    # NAMES only — never values.
    assert "clss.identity.dev.jwt_private_key" in missing


def test_token_service_degrades_without_key():
    svc = TokenService(private_key=None, public_key=None, issuer="i", audience="a",
                       algorithm="RS256", ttl_seconds=60)
    assert svc.can_sign is False


def test_sso_degrades_without_provider_config(monkeypatch):
    for name in ("CLSS_IDENTITY_DEV_GOOGLE_CLIENT_ID", "CLSS_IDENTITY_DEV_SAML_ENTITY_ID",
                 "CLSS_IDENTITY_DEV_SAML_SSO_URL"):
        monkeypatch.delenv(name, raising=False)
    assert sso.provider_configured("google") is False
    started = sso.build_start(provider="google", app="school", redirect_uri=None)
    assert started.degraded is True
    assert "dev.local" in started.authorization_url
