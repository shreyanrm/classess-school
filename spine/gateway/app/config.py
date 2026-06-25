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
    # The deep intelligence engine (mastery / gaps / recommendations / class
    # insights). The ONE source of truth lives in the Python spine and is reached
    # only through the wall. Unset -> route returns 503 and the web surface falls
    # back to its in-browser engine port. clss.gateway.dev.intelligence_base_url
    intelligence_base_url: str | None = Field(default=None)
    # The workflow runtime (spine A5) — the proactive loop + permission ladder.
    # Runs in-process in the single deployable; unset -> the gateway forwards to
    # the in-process /internal/workflow mount when self_base_url is set.
    # clss.gateway.dev.workflow_base_url
    workflow_base_url: str | None = Field(default=None)
    # In the SINGLE DEPLOYABLE the identity + event-store services run in-process
    # and are mounted under {self_base_url}/internal/{name}. When the explicit
    # per-capability base urls are unset, the gateway forwards to these in-process
    # mounts over loopback instead of returning a 503. clss.gateway.dev.self_base_url
    self_base_url: str | None = Field(default=None)

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

    def _internal_mount(self, name: str) -> str | None:
        """In-process loopback target for a spine service mounted under
        ``/internal/<name>`` in the single deployable. ``None`` when no
        ``self_base_url`` is configured (then the explicit per-capability base
        url is the only source)."""
        if not self.self_base_url:
            return None
        return self.self_base_url.rstrip("/") + f"/internal/{name}"

    def capability_targets(self) -> dict[str, CapabilityTarget]:
        # Prefer an explicit per-capability base url; otherwise, in the single
        # deployable, forward to the in-process internal mount over loopback.
        return {
            "identity": CapabilityTarget(
                name="identity",
                base_url=self.identity_base_url or self._internal_mount("identity"),
                base_url_env="clss.gateway.dev.identity_base_url",
            ),
            "event-store": CapabilityTarget(
                name="event-store",
                base_url=self.event_store_base_url or self._internal_mount("event-store"),
                base_url_env="clss.gateway.dev.event_store_base_url",
            ),
            # The deep intelligence engine — one source of truth (the Python
            # spine). Both the learner read (learning) and the cross-context
            # class/recommendation views (intelligence-views) forward here.
            "intelligence": CapabilityTarget(
                name="intelligence",
                base_url=self.intelligence_base_url or self._internal_mount("intelligence"),
                base_url_env="clss.gateway.dev.intelligence_base_url",
            ),
            "learning": CapabilityTarget(
                name="learning",
                base_url=self.intelligence_base_url or self._internal_mount("intelligence"),
                base_url_env="clss.gateway.dev.intelligence_base_url",
            ),
            "intelligence-views": CapabilityTarget(
                name="intelligence-views",
                base_url=self.intelligence_base_url or self._internal_mount("intelligence"),
                base_url_env="clss.gateway.dev.intelligence_base_url",
            ),
            # The workflow runtime (spine A5) — the proactive loop + permission
            # ladder. In the single deployable it runs in-process under
            # /internal/workflow; an explicit base url overrides for a split-out.
            "workflow": CapabilityTarget(
                name="workflow",
                base_url=self.workflow_base_url or self._internal_mount("workflow"),
                base_url_env="clss.gateway.dev.workflow_base_url",
            ),
        }

    def degraded_reasons(self) -> list[str]:
        missing: list[str] = []
        if not self.jwt_public_key and not self.identity_introspect_url:
            missing.append("clss.gateway.dev.jwt_public_key (or clss.gateway.dev.identity_introspect_url)")
        # In-process forwarding (self_base_url) satisfies these upstreams.
        if not self.identity_base_url and not self.self_base_url:
            missing.append("clss.gateway.dev.identity_base_url (or clss.gateway.dev.self_base_url)")
        if not self.event_store_base_url and not self.self_base_url:
            missing.append("clss.gateway.dev.event_store_base_url (or clss.gateway.dev.self_base_url)")
        if not self.database_url:
            missing.append("clss.gateway.dev.database_url (audit sink)")
        return missing


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
