"""Intelligence-views (B11) configuration.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded. Dotted contract names map to ``CLSS_INTELLIGENCE_VIEWS_DEV_*`` env
vars. NEXT_PUBLIC_ is never used for any secret (a view-layer temptation; we
refuse it).

This module composes the proactive loop and the governed semantic layer into
dashboards. It is a VIEW: it holds NO credentials (INVARIANT 8 — agents hold
none), and every cross-service read (the feature store, the governed semantic
layer, the event log) passes the gateway (INVARIANT 3). With no gateway/feature
provider configured the module degrades to the deterministic in-memory inputs the
spine engines already produce — and because the composition is pure, the rendered
view is identical either way, which is exactly what makes the dashboards
reproducible.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]


class IntelligenceViewsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLSS_INTELLIGENCE_VIEWS_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="intelligence-views")

    # --- Gateway (the only egress; every cross-service call passes it) ----
    # The views reach the feature store, the governed semantic layer, and the
    # event log THROUGH the gateway, never directly.
    # clss.intelligence_views.dev.gateway_url
    gateway_url: str | None = Field(default=None)

    # --- Feature store (read-only behind the gateway) --------------------
    # The precomputed projections (mastery, gaps, coverage) the dashboards
    # compose. Unset -> degrade to the deterministic in-memory projections.
    # clss.intelligence_views.dev.feature_store_url
    feature_store_url: str | None = Field(default=None)

    # --- Governed semantic layer (consent- and purpose-gated reads) ------
    # The one-metric-one-definition registry resolution service. Unset -> use
    # the built-in deterministic metric registry (the contract is the registry
    # shape; the definitions are identical either way).
    # clss.intelligence_views.dev.semantic_layer_url
    semantic_layer_url: str | None = Field(default=None)

    # --- Consent service (INVARIANT 6 — every cross-context read gated) ---
    # clss.intelligence_views.dev.consent_service_url
    consent_service_url: str | None = Field(default=None)

    # --- Ask-anything model route (NAME only) ----------------------------
    # Reserved for natural-language -> metric resolution. The view never holds a
    # key; the route name is resolved at the gateway. The deterministic resolver
    # works with no provider; this only names the var a model-assisted resolver
    # would read. NO key value is ever stored here.
    # clss.intelligence_views.dev.ask_model_route (name only)
    ask_model_route: str | None = Field(default=None)

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url)

    @property
    def has_feature_store(self) -> bool:
        return bool(self.feature_store_url)

    def degraded_reasons(self) -> list[str]:
        """Names (never values) of env vars that, if set, would lift degradation.

        Returns dotted contract names only — never a value (INVARIANT 4).
        """
        missing: list[str] = []
        if not self.gateway_url:
            missing.append("clss.intelligence_views.dev.gateway_url")
        if not self.feature_store_url:
            missing.append("clss.intelligence_views.dev.feature_store_url")
        if not self.semantic_layer_url:
            missing.append("clss.intelligence_views.dev.semantic_layer_url")
        if not self.consent_service_url:
            missing.append("clss.intelligence_views.dev.consent_service_url")
        return missing


@lru_cache
def get_settings() -> IntelligenceViewsSettings:
    return IntelligenceViewsSettings()
