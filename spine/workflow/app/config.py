"""Workflow-engine configuration.

INVARIANT 4: secrets are environment-only, read by NAME, never hardcoded or
logged. Dotted contract names map to ``CLSS_WORKFLOW_DEV_*`` env vars.

The workflow engine itself holds NO outward credentials (agents hold none —
INVARIANT 8). It needs only references to the governed services it calls THROUGH
THE GATEWAY: the event store (to read evidence and to append loop events) and
the gateway base. Outward effects (send/submit/publish/delete/charge/grade) are
performed by governed capabilities behind the gateway, not here.

NO live LLM keys or Supabase yet: every deterministic path works without a
provider. The interpreter/builder registry degrades gracefully — absent a
provider, deterministic interpreters still run.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAS_SETTINGS = True
except Exception:  # pragma: no cover - pydantic-settings optional at import time
    from pydantic import BaseModel as BaseSettings  # type: ignore

    SettingsConfigDict = dict  # type: ignore
    _HAS_SETTINGS = False

ENV = Literal["dev", "staging", "prod"]


class WorkflowSettings(BaseSettings):
    if _HAS_SETTINGS:
        model_config = SettingsConfigDict(
            env_prefix="CLSS_WORKFLOW_DEV_",
            env_file=".env",
            extra="ignore",
            case_sensitive=False,
        )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="workflow")

    # --- Every cross-service call passes the gateway (INVARIANT 3) -------
    # clss.workflow.dev.gateway_base_url
    gateway_base_url: str | None = Field(default=None)

    # --- Governed services this engine reads/appends through the gateway --
    # clss.workflow.dev.event_store_url  (read evidence; append loop events)
    event_store_url: str | None = Field(default=None)

    # --- Token verification (PUBLIC key only; defends in depth) ----------
    # clss.workflow.dev.jwt_public_key
    jwt_public_key: str | None = Field(default=None)
    jwt_issuer: str = Field(default="clss.identity")
    jwt_audience: str = Field(default="clss.gateway")
    jwt_algorithm: str = Field(default="RS256")

    # --- Optional AI fabric for second-model cross-checks on interpretation
    # The provider key is NEVER stored here; the gateway holds the route. We
    # only carry the route NAME. clss.workflow.dev.ai_fabric_route
    ai_fabric_route: str | None = Field(default=None)

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_base_url)

    def degraded_reasons(self) -> list[str]:
        """Names of the env vars whose absence keeps the engine on its
        deterministic-only path. Names only — never values."""
        missing: list[str] = []
        if not self.gateway_base_url:
            missing.append("clss.workflow.dev.gateway_base_url")
        if not self.event_store_url:
            missing.append("clss.workflow.dev.event_store_url")
        if not self.jwt_public_key:
            missing.append("clss.workflow.dev.jwt_public_key")
        return missing


@lru_cache
def get_settings() -> WorkflowSettings:
    return WorkflowSettings()
