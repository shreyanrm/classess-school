"""Identity service configuration.

SECURITY INVARIANT 4: secrets are environment-only. This module reads
configuration by env var NAME and NEVER hardcodes a secret value, never
invents a key, and never logs one. Env var names follow the convention
``clss.<app>.<env>.<purpose>``. Because env var names cannot contain dots in
most shells, the dotted canonical name is mapped to an UPPER_SNAKE_CASE
environment variable (e.g. ``clss.identity.dev.supabase_url`` is read from
``CLSS_IDENTITY_DEV_SUPABASE_URL``). Both forms are documented in the README
and the ops inventory.

If a secret/config value is absent the service still imports and starts; the
data layer degrades to a clearly-labelled in-memory adapter so local work and
contract testing are possible without a live Supabase. The env var that is
missing is named in logs (NAME ONLY, never a value).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Canonical dotted env var names (INVARIANT 4 naming). Values are resolved from
# the corresponding UPPER_SNAKE_CASE environment variable at runtime.
ENV = Literal["dev", "staging", "prod"]


class IdentitySettings(BaseSettings):
    """Typed settings for the identity service.

    Every field maps to an UPPER_SNAKE_CASE environment variable. Defaults are
    non-secret and safe for local boot; secrets default to ``None`` so a missing
    one degrades gracefully instead of crashing import.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLSS_IDENTITY_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Non-secret service config ---------------------------------------
    env: ENV = Field(default="dev")
    service_name: str = Field(default="identity")
    # The app namespace this deployment serves (school is the citizen built here).
    app_namespace: str = Field(default="school")

    # --- Supabase / Postgres (PII vault + platform-canonical tables) -----
    # clss.identity.dev.supabase_url
    supabase_url: str | None = Field(default=None)
    # clss.identity.dev.supabase_service_key  (service role; server-side only)
    supabase_service_key: str | None = Field(default=None)
    # clss.identity.dev.supabase_anon_key
    supabase_anon_key: str | None = Field(default=None)
    # clss.identity.dev.database_url  (direct asyncpg connection to Postgres)
    database_url: str | None = Field(default=None)

    # --- Token signing / verification ------------------------------------
    # The identity service MINTS gateway-verifiable tokens. Asymmetric signing:
    # identity holds the private key; the gateway holds only the public key.
    # clss.identity.dev.jwt_private_key  (PEM, RS256). NEVER hardcoded.
    jwt_private_key: str | None = Field(default=None)
    # clss.identity.dev.jwt_public_key   (PEM; also given to the gateway).
    jwt_public_key: str | None = Field(default=None)
    jwt_issuer: str = Field(default="clss.identity")
    jwt_audience: str = Field(default="clss.gateway")
    jwt_algorithm: str = Field(default="RS256")
    token_ttl_seconds: int = Field(default=3600)

    # --- OTP / Redis (rate-limit, OTP challenge store) -------------------
    # clss.identity.dev.redis_url
    redis_url: str | None = Field(default=None)
    otp_ttl_seconds: int = Field(default=300)

    @property
    def has_database(self) -> bool:
        return bool(self.database_url)

    @property
    def can_sign_tokens(self) -> bool:
        return bool(self.jwt_private_key)

    def degraded_reasons(self) -> list[str]:
        """Env var NAMES (never values) that are missing, for startup logs."""
        missing: list[str] = []
        if not self.database_url:
            missing.append("clss.identity.dev.database_url")
        if not self.jwt_private_key:
            missing.append("clss.identity.dev.jwt_private_key")
        if not self.jwt_public_key:
            missing.append("clss.identity.dev.jwt_public_key")
        if not self.redis_url:
            missing.append("clss.identity.dev.redis_url")
        return missing


@lru_cache
def get_settings() -> IdentitySettings:
    return IdentitySettings()
