"""Feature-store configuration.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded. Dotted names map to ``CLSS_FEATURE_STORE_DEV_*`` env vars.

The feature store is a PURE, DETERMINISTIC PROJECTION (spine A3): it computes
derived, versioned features per learner/topic by REPLAYING immutable events, and
forecasts trajectory/exam-readiness/risk from those features. It never authors
features or predictions directly, holds NO credentials, and makes NO external
calls itself.

When no event source is configured (``clss.feature-store.dev.database_url`` /
``clss.feature-store.dev.gateway_url`` unset) it degrades gracefully to an
in-memory event list — the deterministic projection paths work identically
either way, which is exactly what makes feature rebuilds and predictions
reproducible.

INVARIANT 11: Track 1 (external LLM routing) and Track 2 (proprietary / edge
models) stay SEPARATE in config. Both slots exist from the start as NAMES only;
no value is ever stored here. The deterministic forecasting paths work with no
provider in either track.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]


class FeatureStoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLSS_FEATURE_STORE_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="feature-store")

    # --- Event source -----------------------------------------------------
    # The store reads the immutable event log to replay it into features. It
    # NEVER writes events. Unset -> degrade to an in-memory event list.
    # clss.feature-store.dev.database_url
    database_url: str | None = Field(default=None)

    # --- Gateway (the only egress; every cross-service call passes it) ----
    # The store reaches the event store + ontology service THROUGH the gateway,
    # never directly. clss.feature-store.dev.gateway_url
    gateway_url: str | None = Field(default=None)

    # --- Feature projection cache (optional) ------------------------------
    # A materialized feature snapshot may be cached for fast read; absent -> the
    # store recomputes from events each time (still deterministic).
    # clss.feature-store.dev.feature_cache_url
    feature_cache_url: str | None = Field(default=None)

    # --- Track 1: external model router (INVARIANT 11) --------------------
    # Reserved for a future model-assisted forecast cross-check routed to an
    # EXTERNAL provider. Deterministic forecasts work with no provider; this
    # names the var the Track 1 cross-check would read. NO key value stored.
    # clss.feature-store.dev.track1_forecast_model_key (name only)
    track1_forecast_model_key: str | None = Field(default=None)

    # --- Track 2: proprietary / edge model (INVARIANT 11) ----------------
    # The SEPARATE Track 2 slot. Exists from the start, filled later, with no
    # re-architecture. NEVER conflated with Track 1 in config or routing.
    # clss.feature-store.dev.track2_forecast_model_key (name only)
    track2_forecast_model_key: str | None = Field(default=None)

    @property
    def has_event_source(self) -> bool:
        return bool(self.database_url)

    @property
    def has_feature_cache(self) -> bool:
        return bool(self.feature_cache_url)

    def degraded_reasons(self) -> list[str]:
        """Names (never values) of env vars that, if set, would lift degradation."""
        missing: list[str] = []
        if not self.database_url:
            missing.append("clss.feature-store.dev.database_url")
        if not self.gateway_url:
            missing.append("clss.feature-store.dev.gateway_url")
        if not self.feature_cache_url:
            missing.append("clss.feature-store.dev.feature_cache_url")
        return missing


@lru_cache
def get_settings() -> FeatureStoreSettings:
    return FeatureStoreSettings()
