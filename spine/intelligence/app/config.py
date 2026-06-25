"""Intelligence engine configuration.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded. Dotted names map to ``CLSS_INTELLIGENCE_DEV_*`` env vars.

The engine is PURE and DETERMINISTIC: it computes derived state by replaying
events. It holds NO credentials and makes NO external calls itself. When the
event source (``clss.intelligence.dev.database_url``) is unset it degrades
gracefully to an in-memory event list — the deterministic projection paths work
identically either way, which is exactly what makes rebuilds reproducible.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]


class IntelligenceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLSS_INTELLIGENCE_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="intelligence")

    # --- Event source -----------------------------------------------------
    # The engine reads the immutable event log to replay it. It NEVER writes
    # events. Unset -> degrade to an in-memory event list (tests, local dev).
    # clss.intelligence.dev.database_url
    database_url: str | None = Field(default=None)

    # --- Gateway (the only egress; every cross-service call passes it) ----
    # The engine reaches the event store + ontology service THROUGH the gateway,
    # never directly. clss.intelligence.dev.gateway_url
    gateway_url: str | None = Field(default=None)

    # Bearer issued by identity (A1), presented at the gateway wall. NEVER a
    # literal; read from the environment by name only (INVARIANT 4, 8).
    # clss.intelligence.dev.gateway_token
    gateway_token: str | None = Field(default=None)

    # Where derived-state events (mastery.updated / gap.detected / gap.resolved)
    # are POSTed THROUGH the gateway. Unset -> emission degrades to an in-memory
    # append-only sink. Events are the ONLY thing this engine writes, and only as
    # a projection of what it derived. clss.intelligence.dev.event_sink_url
    event_sink_url: str | None = Field(default=None)

    # --- Second-model cross-check (generate-and-verify, INVARIANT 7) ------
    # Reserved for a future model-assisted gap cross-check. The engine's gap
    # rules are deterministic and work with no provider; this names the var a
    # cross-check would read. NO key value is ever stored here.
    # clss.intelligence.dev.crosscheck_model_key (name only)
    crosscheck_model_key: str | None = Field(default=None)

    @property
    def has_event_source(self) -> bool:
        return bool(self.database_url)

    @property
    def has_event_sink(self) -> bool:
        """True only when the gateway AND a sink are configured — every write
        passes the gateway, so a sink URL without a gateway is still degraded."""
        return bool(self.gateway_url and self.gateway_token and self.event_sink_url)

    def degraded_reasons(self) -> list[str]:
        """Names (never values) of env vars that, if set, would lift degradation."""
        missing: list[str] = []
        if not self.database_url:
            missing.append("clss.intelligence.dev.database_url")
        if not self.gateway_url:
            missing.append("clss.intelligence.dev.gateway_url")
        return missing


@lru_cache
def get_settings() -> IntelligenceSettings:
    return IntelligenceSettings()
