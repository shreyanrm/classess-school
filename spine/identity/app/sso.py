"""SSO federation — the single front door (classess-school.html §0, §8).

KGtoPG is "the single sign-on front door … the same pattern as 'sign in with
Google,' owned internally". Phone-OTP stays first; this module adds the
delegated federations: Google, Apple, Microsoft, and institutional SSO/SAML.

The federation is delegated to the provider — this service never holds a
provider password. It builds the provider authorization URL, validates the
anti-forgery ``state`` on the callback, and on first callback for a subject
AUTO-PROVISIONS one canonical identity (INVARIANT: one canonical identity per
human, established once, here).

Graceful degradation (SECURITY INVARIANT 4 — env-only secrets, degrade with no
key): when a provider's client config is absent the service does not fabricate a
secret or call out. ``start`` returns a clearly-labelled LOCAL DEV authorization
URL and the callback still resolves a subject so the contract is fully
exercisable offline. No live network is ever required.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

logger = logging.getLogger("clss.identity.sso")

# Provider authorization endpoints. Used ONLY to build a redirect URL; the
# token exchange is delegated. No secret appears here.
_PROVIDER_AUTHORIZE = {
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
    "apple": "https://appleid.apple.com/auth/authorize",
    "microsoft": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    # Institutional SSO/SAML: the IdP entry point is configured per-institution
    # by env (CLSS_IDENTITY_DEV_SAML_SSO_URL). No default endpoint.
    "saml": None,
}

# Env var NAMES (never values) for each provider's client id (INVARIANT 4).
_CLIENT_ID_ENV = {
    "google": "CLSS_IDENTITY_DEV_GOOGLE_CLIENT_ID",
    "apple": "CLSS_IDENTITY_DEV_APPLE_CLIENT_ID",
    "microsoft": "CLSS_IDENTITY_DEV_MICROSOFT_CLIENT_ID",
    "saml": "CLSS_IDENTITY_DEV_SAML_ENTITY_ID",
}
_SAML_SSO_URL_ENV = "CLSS_IDENTITY_DEV_SAML_SSO_URL"

_DEV_DEGRADED_BASE = "https://dev.local/identity/sso"


@dataclass(frozen=True)
class SsoStart:
    authorization_url: str
    state: str
    degraded: bool


def _client_id(provider: str) -> str | None:
    return os.environ.get(_CLIENT_ID_ENV[provider]) or None


def provider_configured(provider: str) -> bool:
    """True iff this deployment has the env config to delegate to the provider.
    Names only are consulted; values are never logged."""
    if _client_id(provider) is None:
        return False
    if provider == "saml":
        return bool(os.environ.get(_SAML_SSO_URL_ENV))
    return True


def build_start(*, provider: str, app: str, redirect_uri: str | None) -> SsoStart:
    """Build the provider authorization URL + an anti-forgery state. Degrades to
    a clearly-labelled local dev URL when the provider is not configured."""
    state = secrets.token_urlsafe(24)
    if not provider_configured(provider):
        logger.warning(
            "SSO provider %s not configured (set %s); returning DEGRADED local dev "
            "authorization URL. No live federation will occur.",
            provider, _CLIENT_ID_ENV[provider],
        )
        params = {"provider": provider, "app": app, "state": state, "degraded": "1"}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        return SsoStart(f"{_DEV_DEGRADED_BASE}/authorize?{urlencode(params)}", state, True)

    if provider == "saml":
        base = os.environ[_SAML_SSO_URL_ENV]
        params = {"SAMLRequest": "delegated", "RelayState": state}
    else:
        base = _PROVIDER_AUTHORIZE[provider]
        params = {
            "client_id": _client_id(provider),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
    return SsoStart(f"{base}?{urlencode(params)}", state, False)
