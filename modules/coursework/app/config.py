"""Coursework & assessment configuration (B6).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded or logged. The dotted convention is ``clss.<app>.<env>.<purpose>``;
``env_var_name`` maps a dotted secret name to its OS environment key. This module
NEVER reads a secret VALUE at import; it only knows the NAMES, and degrades
gracefully (clear interfaces, deterministic paths) when a provider is absent.

No live LLM keys or Supabase yet. Generation routes through the AI fabric's
generate-and-verify substrate (which itself returns a clean refusal with no
provider), and event emission degrades to returning the event object when no
event store is wired.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]

# The canonical secret-name convention. The dotted name is the source of truth;
# env_var_name() maps it to an OS-safe key.
DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.coursework.dev.event_store_url`` -> ``CLSS_COURSEWORK_DEV_EVENT_STORE_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


class CourseworkSettings(BaseSettings):
    """Coursework module settings.

    Every field that would carry a secret is OPTIONAL and defaults to ``None``;
    the module runs fully in a degraded, deterministic mode without any of them.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLSS_COURSEWORK_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="coursework")

    # --- Event store (emit via its interface; degrade to returning the event) ---
    # clss.coursework.dev.event_store_url
    event_store_url: str | None = Field(default=None)

    # --- Gateway (every cross-service call passes the gateway; INVARIANT 9) ---
    # clss.coursework.dev.gateway_url
    gateway_url: str | None = Field(default=None)
    # clss.coursework.dev.gateway_token  (bearer issued by identity; NEVER hardcoded)
    gateway_token: str | None = Field(default=None)

    # --- AI fabric (paper generation routes through generate-and-verify) ------
    # clss.coursework.dev.ai_fabric_url
    ai_fabric_url: str | None = Field(default=None)

    # --- OCR provider (scanned-handwriting mode; interface only, no key yet) --
    # clss.coursework.dev.ocr_provider_key
    ocr_provider_key: str | None = Field(default=None)

    # --- Originality / similarity provider (interface only, no key yet) -------
    # clss.coursework.dev.originality_provider_key
    originality_provider_key: str | None = Field(default=None)

    @property
    def has_event_store(self) -> bool:
        return bool(self.event_store_url)

    @property
    def has_ocr_provider(self) -> bool:
        return bool(self.ocr_provider_key)

    @property
    def has_originality_provider(self) -> bool:
        return bool(self.originality_provider_key)

    def degraded_reasons(self) -> list[str]:
        """Dotted NAMES of the secrets that are absent — for clear logging.

        Never returns a value, only the name a deployer must set.
        """
        missing: list[str] = []
        if not self.event_store_url:
            missing.append("clss.coursework.dev.event_store_url")
        if not self.gateway_url:
            missing.append("clss.coursework.dev.gateway_url")
        if not self.ai_fabric_url:
            missing.append("clss.coursework.dev.ai_fabric_url")
        if not self.ocr_provider_key:
            missing.append("clss.coursework.dev.ocr_provider_key")
        if not self.originality_provider_key:
            missing.append("clss.coursework.dev.originality_provider_key")
        return missing


@lru_cache
def get_settings() -> CourseworkSettings:
    return CourseworkSettings()
