"""Gateway configuration — including the TWO-TRACK routing structure.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded or logged. Dotted names map to ``CLSS_GATEWAY_DEV_*`` env vars.

SECURITY INVARIANT 11: the two tracks are NEVER conflated. ``TrackConfig`` has
two distinct sections — ``track1`` (external LLM routing, present now) and
``track2`` (proprietary / edge models, the slot exists now and is filled
later). They are separate objects with separate ownership and separate config;
adding Track 2 models is a config change, not a re-architecture.

The gateway holds only the PUBLIC key to verify identity tokens — never the
private signing key.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]


class CapabilityTarget(BaseModel):
    """Where a routed capability lives. The gateway is the only caller."""

    name: str
    base_url: str | None = Field(
        default=None,
        description="Upstream base URL. None => degraded: route returns 503 with the env var name to set.",
    )
    base_url_env: str = Field(description="Env var NAME that supplies base_url (INVARIANT 4).")


class Track1Config(BaseModel):
    """External LLM routing (LiteLLM, Ring 1). Present now; the gateway only
    holds the routing endpoint NAME — provider keys live behind the router and
    are never seen by the gateway."""

    enabled: bool = Field(default=False)
    router_base_url: str | None = Field(default=None)
    router_base_url_env: str = Field(default="clss.gateway.dev.track1_router_url")
    # The provider key is held by the router, not the gateway. Named for ops.
    provider_keys_owner: str = Field(default="ai-fabric router (Ring 1)")


class Track2Config(BaseModel):
    """Proprietary / edge models. INVARIANT 11: the slot exists from line one,
    filled later, no re-architecture. Distinct ownership from Track 1."""

    enabled: bool = Field(default=False)
    endpoint_base_url: str | None = Field(default=None)
    endpoint_base_url_env: str = Field(default="clss.gateway.dev.track2_endpoint_url")
    owner: str = Field(default="proprietary models team (Ring 2)")
    note: str = Field(default="Reserved. Filled in Ring 2. Separate ownership and config from Track 1.")


class TrackConfig(BaseModel):
    """The two tracks, kept structurally separate (INVARIANT 11)."""

    track1: Track1Config = Field(default_factory=Track1Config)
    track2: Track2Config = Field(default_factory=Track2Config)


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLSS_GATEWAY_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="gateway")

    # --- Token verification (PUBLIC key only; never the private key) -----
    # clss.gateway.dev.jwt_public_key
    jwt_public_key: str | None = Field(default=None)
    jwt_issuer: str = Field(default="clss.identity")
    jwt_audience: str = Field(default="clss.gateway")
    jwt_algorithm: str = Field(default="RS256")
    # Fallback path: ask the identity service to introspect when no public key
    # is configured. clss.gateway.dev.identity_introspect_url
    identity_introspect_url: str | None = Field(default=None)

    # --- Capability upstreams (routing targets) --------------------------
    # clss.gateway.dev.identity_base_url
    identity_base_url: str | None = Field(default=None)
    # clss.gateway.dev.event_store_base_url
    event_store_base_url: str | None = Field(default=None)

    # --- Audit sink ------------------------------------------------------
    # clss.gateway.dev.database_url  (writes platform.audit_log; INVARIANT 9)
    database_url: str | None = Field(default=None)

    # --- Two-track routing (INVARIANT 11) --------------------------------
    track1_router_url: str | None = Field(default=None)
    track2_endpoint_url: str | None = Field(default=None)

    def tracks(self) -> TrackConfig:
        return TrackConfig(
            track1=Track1Config(
                enabled=bool(self.track1_router_url),
                router_base_url=self.track1_router_url,
            ),
            track2=Track2Config(
                enabled=bool(self.track2_endpoint_url),
                endpoint_base_url=self.track2_endpoint_url,
            ),
        )

    def capability_targets(self) -> dict[str, CapabilityTarget]:
        return {
            "identity": CapabilityTarget(
                name="identity",
                base_url=self.identity_base_url,
                base_url_env="clss.gateway.dev.identity_base_url",
            ),
            "event-store": CapabilityTarget(
                name="event-store",
                base_url=self.event_store_base_url,
                base_url_env="clss.gateway.dev.event_store_base_url",
            ),
        }

    def degraded_reasons(self) -> list[str]:
        missing: list[str] = []
        if not self.jwt_public_key and not self.identity_introspect_url:
            missing.append("clss.gateway.dev.jwt_public_key (or clss.gateway.dev.identity_introspect_url)")
        if not self.identity_base_url:
            missing.append("clss.gateway.dev.identity_base_url")
        if not self.event_store_base_url:
            missing.append("clss.gateway.dev.event_store_base_url")
        if not self.database_url:
            missing.append("clss.gateway.dev.database_url (audit sink)")
        return missing


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
