"""Event-store configuration.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded or logged. Dotted names map to ``CLSS_EVENTSTORE_DEV_*`` env vars.

The store verifies the identity token with the PUBLIC key (it sits behind the
gateway, but defends in depth and never trusts an unauthenticated caller).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]


class EventStoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLSS_EVENTSTORE_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="event-store")

    # --- Postgres (platform.events + governed read functions) -----------
    # clss.eventstore.dev.database_url
    database_url: str | None = Field(default=None)
    # clss.eventstore.dev.supabase_url / supabase_service_key (Supabase mechanism)
    supabase_url: str | None = Field(default=None)
    supabase_service_key: str | None = Field(default=None)

    # --- Token verification (PUBLIC key only) ---------------------------
    # clss.eventstore.dev.jwt_public_key
    jwt_public_key: str | None = Field(default=None)
    jwt_issuer: str = Field(default="clss.identity")
    jwt_audience: str = Field(default="clss.gateway")
    jwt_algorithm: str = Field(default="RS256")

    # --- Consent gate ----------------------------------------------------
    # The store can re-check consent against the identity service for defense in
    # depth. clss.eventstore.dev.identity_consent_check_url
    identity_consent_check_url: str | None = Field(default=None)

    @property
    def has_database(self) -> bool:
        return bool(self.database_url)

    def degraded_reasons(self) -> list[str]:
        missing: list[str] = []
        if not self.database_url:
            missing.append("clss.eventstore.dev.database_url")
        if not self.jwt_public_key:
            missing.append("clss.eventstore.dev.jwt_public_key")
        return missing


@lru_cache
def get_settings() -> EventStoreSettings:
    return EventStoreSettings()
