"""Integration (FLUID) configuration — spine A6.

INVARIANT 4: secrets are environment-only, read by NAME, never hardcoded or
logged. Dotted contract names map to ``CLSS_INTEGRATION_DEV_*`` env vars.

The integration layer holds NO connector credentials of its own. Adapters here
describe a connection and translate payloads; the actual outbound call is made
by a governed, credentialled capability BEHIND THE GATEWAY (INVARIANT 3, 8).
This module only carries the route NAMES it needs and the public verification
key (defence in depth). Absent any config every adapter still parses, maps, and
round-trips against fixtures in a clearly-labelled DEGRADED mode.

INVARIANT 11: Track 1 (external standards endpoints / external LLM routing) and
Track 2 (proprietary / edge) are kept in structurally separate fields so a
later Track 2 fill is a config change, not a re-architecture.
"""

from __future__ import annotations

import os
from functools import lru_cache

ENV_PREFIX = "CLSS_INTEGRATION_DEV_"
DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret NAME to its OS environment variable key.

    ``clss.integration.dev.gateway_base_url`` -> ``CLSS_INTEGRATION_DEV_GATEWAY_BASE_URL``.
    Used only to LOOK UP a value by name; the value itself is never logged.
    """

    return dotted.replace(".", "_").upper()


def _read(field: str) -> str | None:
    """Read a single config field from the env by its prefixed NAME."""

    return os.environ.get(ENV_PREFIX + field.upper())


class IntegrationSettings:
    """Runtime config resolved from the environment by NAME only.

    Plain stdlib (no pydantic dependency) so the package is import-safe and the
    suite runs with no third-party installs, no network, and no DB.
    """

    env: str = "dev"
    service_name: str = "integration"

    # JWT issuer/audience/algorithm defaults (token VERIFY only, public key).
    jwt_issuer: str = "clss.identity"
    jwt_audience: str = "clss.gateway"
    jwt_algorithm: str = "RS256"

    def __init__(self) -> None:
        # --- Every cross-service call passes the gateway (INVARIANT 3) ----
        # clss.integration.dev.gateway_base_url
        self.gateway_base_url: str | None = _read("gateway_base_url")

        # --- Governed services this layer reads/appends THROUGH the gateway
        # clss.integration.dev.event_store_url   (append xAPI/Caliper as events)
        self.event_store_url: str | None = _read("event_store_url")
        # clss.integration.dev.identity_base_url (resolve canonical identity)
        self.identity_base_url: str | None = _read("identity_base_url")
        # clss.integration.dev.ontology_base_url (map outcomes/CASE into ontology)
        self.ontology_base_url: str | None = _read("ontology_base_url")

        # --- Token verification (PUBLIC key only; defends in depth) -------
        # clss.integration.dev.jwt_public_key
        self.jwt_public_key: str | None = _read("jwt_public_key")

        # --- Connector route NAMES (Track 1 = external standards endpoints) -
        # The credentials live with the governed capability behind the gateway;
        # we only know the ROUTE NAME to invoke. None of these are secrets.
        # clss.integration.dev.lti_platform_issuer
        self.lti_platform_issuer: str | None = _read("lti_platform_issuer")
        # clss.integration.dev.lti_jwks_url
        self.lti_jwks_url: str | None = _read("lti_jwks_url")
        # clss.integration.dev.oneroster_base_url
        self.oneroster_base_url: str | None = _read("oneroster_base_url")
        # clss.integration.dev.clever_base_url
        self.clever_base_url: str | None = _read("clever_base_url")
        # clss.integration.dev.classlink_base_url
        self.classlink_base_url: str | None = _read("classlink_base_url")
        # clss.integration.dev.edfi_base_url
        self.edfi_base_url: str | None = _read("edfi_base_url")
        # clss.integration.dev.case_registry_url
        self.case_registry_url: str | None = _read("case_registry_url")
        # clss.integration.dev.caliper_endpoint_url
        self.caliper_endpoint_url: str | None = _read("caliper_endpoint_url")
        # clss.integration.dev.xapi_lrs_url
        self.xapi_lrs_url: str | None = _read("xapi_lrs_url")

        # --- Track 2 (proprietary / edge) — reserved slot, filled later ----
        # clss.integration.dev.track2_connector_url
        self.track2_connector_url: str | None = _read("track2_connector_url")

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_base_url)

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_reasons())

    def degraded_reasons(self) -> list[str]:
        """Names of env vars whose absence keeps the layer on its offline,
        fixture-driven path. NAMES ONLY — never values (INVARIANT 4)."""

        missing: list[str] = []
        if not self.gateway_base_url:
            missing.append("clss.integration.dev.gateway_base_url")
        if not self.event_store_url:
            missing.append("clss.integration.dev.event_store_url")
        if not self.jwt_public_key:
            missing.append("clss.integration.dev.jwt_public_key")
        return missing


@lru_cache
def get_settings() -> IntegrationSettings:
    return IntegrationSettings()
